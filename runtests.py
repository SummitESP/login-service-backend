#!/usr/bin/env python
import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def main():
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    django.setup()
    TestRunner = get_runner(settings)
    failures = TestRunner(verbosity=1).run_tests(["tests"])
    sys.exit(bool(failures))


if __name__ == "__main__":
    main()
