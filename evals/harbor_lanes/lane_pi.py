"""Harbor agent: Pi (npm 1.5.0, same version as vendors/pi) with the lane-router extension loaded.

Usage (from evals/):
  harbor run -p <task> -a harbor_lanes.lane_pi:LanePi -m lanes/auto --resume-trajectory ...       # our router
  harbor run -p <task> -a harbor_lanes.lane_pi:LanePi -m meta/muse-wonder-1.0 --resume-trajectory  # always-biggest

Keys come from the host environment (source ../.env first). The extension is inert unless the selected
model is lanes/*, so both configs run the exact same Pi build.
"""

import os
import shlex
from pathlib import Path, PurePosixPath
from typing import override

from harbor.agents.installed.pi import Pi
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

PI_VERSION = "1.5.0"
EXTENSION_SOURCE = Path(__file__).resolve().parents[2] / "extensions" / "lane-router"
REMOTE_EXTENSION_DIR = PurePosixPath("/tmp/lane-router")
FORWARDED_ENV = ("SUBQ_API_KEY", "META_API_KEY", "GEMINI_API_KEY", "LANES_MAPPING")


class LanePi(Pi):
    @classmethod
    @override
    def check_model_credentials(cls, connection, *, kwargs, env, explicit_env=None):
        # Credentials are forwarded explicitly in run(); lanes/* is a virtual provider Harbor doesn't know.
        return None

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        self._version = PI_VERSION
        await super().install(environment)
        await environment.upload_dir(EXTENSION_SOURCE, REMOTE_EXTENSION_DIR.as_posix())
        await environment.exec(command=f"chmod -R a+rX {shlex.quote(REMOTE_EXTENSION_DIR.as_posix())}")

    @override
    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model must be provider/model, e.g. lanes/auto or meta/muse-wonder-1.0")
        provider, model_id = self.model_name.split("/", 1)
        env = {name: os.environ[name] for name in FORWARDED_ENV if os.environ.get(name)}

        session_dir = self.environment_logs_dir / self._SESSIONS_DIRECTORY
        output_path = self.environment_logs_dir / self._OUTPUT_FILENAME
        resume_flag = "--continue " if self._resume else ""
        self._session_usage_start = await self._session_positions(environment) if self._resume else {}
        extension = (REMOTE_EXTENSION_DIR / "index.ts").as_posix()

        await self.exec_as_agent(
            environment,
            command=(
                ". ~/.nvm/nvm.sh; "
                f"mkdir -p {shlex.quote(str(session_dir))} && "
                "pi --print --mode json "
                f"--session-dir {shlex.quote(str(session_dir))} "
                f"{resume_flag}"
                f"--provider {shlex.quote(provider)} --model {shlex.quote(model_id)} "
                f"--extension {shlex.quote(extension)} "
                f"{shlex.quote(instruction)} "
                "2>&1 </dev/null | grep -v '\"type\":\"message_update\"' "
                f"| stdbuf -oL tee -a {shlex.quote(str(output_path))}; "
                # Keep the router's per-turn log next to Harbor's logs for cost analysis.
                f"cp -r .lanes {shlex.quote(str(self.environment_logs_dir))}/lanes 2>/dev/null || true"
            ),
            env=env,
        )
