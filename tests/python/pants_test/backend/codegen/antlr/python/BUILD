# Copyright 2016 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).


python_tests(
  sources = globs('*.py', exclude=[globs('*_integration.py')]),
  dependencies = [
    '3rdparty/python/twitter/commons:twitter.common.dirutil',
    'src/python/pants/backend/codegen/antlr/python',
    'src/python/pants/base:exceptions',
    'src/python/pants/build_graph',
    'tests/python/pants_test:test_base',
    'tests/python/pants_test/jvm:nailgun_task_test_base',
  ]
)


python_tests(
  name = 'integration',
  sources = globs('*_integration.py'),
  dependencies = [
    'tests/python/pants_test:int-test',
    'tests/python/pants_test/backend/python:interpreter_selection_utils',
  ],
  tags = {'integration'},
)
