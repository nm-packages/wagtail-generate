# Releasing

GitHub Actions runs the project checks on pushes and pull requests to `main`.
The release-related local check builds both package formats from a source archive
and verifies their license files and metadata:

```shell
WAGTAIL_GENERATE_TEST_DISTRIBUTION=1 uv run pytest tests/test_distribution.py
```

The project uses the MIT license in `LICENSE`. Release archives must include its
full text and copyright notice, with matching package metadata.

The distribution check may need network access to install the build backend. The
ordinary test suite skips it unless
`WAGTAIL_GENERATE_TEST_DISTRIBUTION=1` is set.
