import asyncio
import signal
import sys
from pathlib import Path

import grpc
from grpc_health.v1 import health_pb2_grpc, health_pb2
from grpc_reflection.v1alpha import reflection

from app.config import settings, Environment
from app.core.logger import logger
from app.rpc_server import FileServiceRpc, HealthCheckServicer

# Make generated protobufs importable when running as a script.
GEN_PATH = Path(__file__).resolve().parent / "app" / "rpc_server" / "gen" / "python"
if str(GEN_PATH) not in sys.path:
    sys.path.insert(0, str(GEN_PATH))

from files.v1 import files_pb2, files_pb2_grpc  # noqa: E402


class GracefulServer:
    def __init__(self):
        self.server: grpc.aio.Server | None = None
        self.shutdown_event = asyncio.Event()

    async def setup_server(self):
        self.server = grpc.aio.server()
        listen_addr = f"[::]:{settings.GRPC_SERVER_PORT}"

        self.server.add_insecure_port(listen_addr)

        files_pb2_grpc.add_FileServiceServicer_to_server(FileServiceRpc(), self.server)
        health_pb2_grpc.add_HealthServicer_to_server(HealthCheckServicer(), self.server)

        if settings.ENVIRONMENT == Environment.DEVELOPMENT:
            try:
                service_names = [
                    files_pb2.DESCRIPTOR.services_by_name["FileService"].full_name,
                    health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
                    reflection.SERVICE_NAME,
                ]
                reflection.enable_server_reflection(service_names, self.server)
                logger.info("gRPC reflection enabled for development")
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.warning("Failed to enable reflection", error=str(exc))

        logger.info("gRPC server configured", address=listen_addr)

    def setup_signal_handlers(self):
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal", signal=signum)
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    async def shutdown(self):
        if not self.shutdown_event.is_set():
            self.shutdown_event.set()

    async def serve(self):
        await self.setup_server()
        self.setup_signal_handlers()

        await self.server.start()
        logger.info("gRPC server started")

        try:
            await self.shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("Server cancelled")
        finally:
            logger.info("Shutting down gRPC server...")
            await self.server.stop(grace=10.0)
            logger.info("Server stopped")


async def main():
    server = GracefulServer()
    try:
        await server.serve()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("Server error", error=str(exc), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
