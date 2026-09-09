"""Build and exercise installed distributions, including legacy-host build isolation."""

import argparse
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--django", default="Django>=5.2,<5.3")
    parser.add_argument("--drf", default="djangorestframework>=3.16,<3.19")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("DJANGO_SETTINGS_MODULE", None)

    with tempfile.TemporaryDirectory(prefix="login-backend-packaging-") as temporary:
        work = Path(temporary)
        dist = work / "dist"
        # By default build creates the wheel FROM the sdist, catching missing source files.
        subprocess.run(
            [sys.executable, "-m", "build", "--outdir", str(dist), str(root)],
            cwd=work,
            env=env,
            check=True,
        )
        artifacts = [*dist.glob("*.whl"), *dist.glob("*.tar.gz")]
        if len(artifacts) != 2:
            raise RuntimeError(f"Expected a wheel and an sdist, found: {artifacts}")
        for index, artifact in enumerate(artifacts):
            target = work / f"installed-{index}"
            venv.EnvBuilder(with_pip=True).create(target)
            python = target / "bin" / "python"

            def run(*command, python=python):
                subprocess.run([str(python), *command], cwd=work, env=env, check=True)

            # Deliberately leave an incompatible setuptools in the host environment.
            run("-m", "pip", "install", "pip==25.2", "setuptools==57.5.0")
            run("-m", "pip", "install", f"{artifact}[drf]", args.django, args.drf)
            run("-m", "pip", "check")
            # -I prevents a source checkout or PYTHONPATH from masking a broken wheel.
            run("-I", str(root / "tests" / "test_installed_backend.py"), "-v")


if __name__ == "__main__":
    main()
