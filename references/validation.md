# Validation

See [release acceptance](../docs/validation.md) for the current verification scope and limits. The reproducible suites are:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_workspace.js
node tests/test_settings.js
node tests/test_drop.js
```

Use a temporary datastore for mutation tests. The optional [demo generator](../examples/create_demo.py) creates synthetic charts and a separate library from explicit new output/data paths. It does not read a personal image collection.
