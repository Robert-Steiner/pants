# Copyright 2019 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

python_binary(
  name='service',
  dependencies=[
    'examples/3rdparty/python:grpcio',
    'examples/src/protobuf/org/pantsbuild/example/grpcio/service',
  ],
  source='service_client.py',
)

python_binary(
  name='imports',
  dependencies=[
    'examples/3rdparty/python:grpcio',
    'examples/src/protobuf/org/pantsbuild/example/grpcio/imports',
  ],
  source='imports_client.py',
)
