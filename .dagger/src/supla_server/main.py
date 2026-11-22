"""Build and test the SUPLA Server app for Home Assistant."""

from datetime import UTC, datetime
from typing import Annotated

import dagger
from dagger import DefaultPath, Doc, Ignore, dag, function, object_type

MOSQUITTO_IMAGE = "eclipse-mosquitto:2.0.22"
PYTHON_IMAGE = "python:3.13-alpine"

Source = Annotated[
    dagger.Directory,
    DefaultPath("/"),
    Ignore([".git", ".dagger", "tests/.data", "**/.DS_Store"]),
    Doc("Repository root"),
]


@object_type
class SuplaServer:
    @function
    def build(self, source: Source) -> dagger.Container:
        """Build the app image from supla_server/Dockerfile."""
        return source.directory("supla_server").docker_build()

    @function
    def mqtt(self) -> dagger.Service:
        """Mosquitto broker that accepts anonymous clients."""
        return (
            dag.container()
            .from_(MOSQUITTO_IMAGE)
            .with_new_file(
                "/mosquitto/config/mosquitto.conf",
                "listener 1883\nallow_anonymous true\n",
            )
            .with_exposed_port(1883)
            .as_service(use_entrypoint=True)
        )

    @function
    def supervisor(self, source: Source, options: dagger.File) -> dagger.Service:
        """Stub Supervisor API (tests/mock_supervisor.py) serving the given app options."""
        return (
            dag.container()
            .from_(PYTHON_IMAGE)
            .with_file("/mock.py", source.file("tests/mock_supervisor.py"))
            .with_file("/options.json", options)
            .with_env_variable("MQTT_HOST", "mqtt")
            .with_exposed_port(80)
            .as_service(args=["python", "-u", "/mock.py"])
        )

    @function
    def app(
        self,
        source: Source,
        options: Annotated[
            dagger.File | None, Doc("App options; defaults to tests/options.json")
        ] = None,
    ) -> dagger.Container:
        """The app container next to a stub Supervisor and Mosquitto, ready to run /init."""
        options = options or source.file("tests/options.json")
        return (
            self.build(source)
            .with_service_binding("supervisor", self.supervisor(source, options))
            .with_service_binding("mqtt", self.mqtt())
            .with_env_variable("SUPERVISOR_TOKEN", "test")
            # Fail instead of hanging when a service never becomes ready (ms).
            .with_env_variable("S6_CMD_WAIT_FOR_SERVICES_MAXTIME", "300000")
            .with_directory("/data", dag.directory())
            .with_file("/data/options.json", options)
        )

    @function(cache="never")
    async def smoke_test(
        self,
        source: Source,
        options: Annotated[
            dagger.File | None, Doc("App options; defaults to tests/options.json")
        ] = None,
    ) -> str:
        """Start the app, check it serves its UI and ports, and that no service crashes.

        Runs tests/smoke.py as the container's main command under s6-overlay.
        Fails if the app's init fails or any check fails.
        """
        return await (
            self.app(source, options)
            # The app image has no Python; add Debian's, in the test container only.
            .with_exec(
                [
                    "sh", "-c",
                    (
                        "apt-get update && apt-get install -y --no-install-recommends python3"
                        " && rm -rf /var/lib/apt/lists/*"
                    ),
                ],
            )
            .with_file("/smoke.py", source.file("tests/smoke.py"))
            .with_env_variable("SMOKE_RUN_AT", datetime.now(UTC).isoformat())
            # s6-overlay must be pid 1, so skip Dagger's own init process.
            .with_exec(["/init", "python3", "-u", "/smoke.py"], no_init=True)
            .stdout()
        )
