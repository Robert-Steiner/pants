# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

import logging
from builtins import object, str
from collections import namedtuple

from twitter.common.collections import OrderedSet

from pants.base.deprecated import deprecated
from pants.base.parse_context import ParseContext
from pants.build_graph.addressable import AddressableCallProxy
from pants.build_graph.build_file_aliases import BuildFileAliases
from pants.build_graph.target_addressable import TargetAddressable
from pants.engine.rules import RuleIndex
from pants.option.optionable import Optionable
from pants.subsystem.subsystem import Subsystem
from pants.util.collections_abc_backport import Iterable
from pants.util.memo import memoized_method


logger = logging.getLogger(__name__)


class BuildConfiguration(object):
  """Stores the types and helper functions exposed to BUILD files."""

  class ParseState(namedtuple('ParseState', ['parse_context', 'parse_globals'])):
    @property
    def objects(self):
      return self.parse_context._storage.objects

  def __init__(self):
    self._target_by_alias = {}
    self._target_macro_factory_by_alias = {}
    self._exposed_object_by_alias = {}
    self._exposed_context_aware_object_factory_by_alias = {}
    self._optionables = OrderedSet()
    self._rules = OrderedSet()

  def registered_aliases(self):
    """Return the registered aliases exposed in BUILD files.

    These returned aliases aren't so useful for actually parsing BUILD files.
    They are useful for generating things like http://pantsbuild.github.io/build_dictionary.html.

    :returns: A new BuildFileAliases instance containing this BuildConfiguration's registered alias
              mappings.
    :rtype: :class:`pants.build_graph.build_file_aliases.BuildFileAliases`
    """
    target_factories_by_alias = self._target_by_alias.copy()
    target_factories_by_alias.update(self._target_macro_factory_by_alias)
    return BuildFileAliases(
        targets=target_factories_by_alias,
        objects=self._exposed_object_by_alias.copy(),
        context_aware_object_factories=self._exposed_context_aware_object_factory_by_alias.copy()
    )

  def register_aliases(self, aliases):
    """Registers the given aliases to be exposed in parsed BUILD files.

    :param aliases: The BuildFileAliases to register.
    :type aliases: :class:`pants.build_graph.build_file_aliases.BuildFileAliases`
    """
    if not isinstance(aliases, BuildFileAliases):
      raise TypeError('The aliases must be a BuildFileAliases, given {}'.format(aliases))

    for alias, target_type in aliases.target_types.items():
      self._register_target_alias(alias, target_type)

    for alias, target_macro_factory in aliases.target_macro_factories.items():
      self._register_target_macro_factory_alias(alias, target_macro_factory)

    for alias, obj in aliases.objects.items():
      self._register_exposed_object(alias, obj)

    for alias, context_aware_object_factory in aliases.context_aware_object_factories.items():
      self._register_exposed_context_aware_object_factory(alias, context_aware_object_factory)

  # TODO(John Sirois): Warn on alias override across all aliases since they share a global
  # namespace in BUILD files.
  # See: https://github.com/pantsbuild/pants/issues/2151
  def _register_target_alias(self, alias, target_type):
    if alias in self._target_by_alias:
      logger.debug('Target alias {} has already been registered. Overwriting!'.format(alias))

    self._target_by_alias[alias] = target_type
    self.register_optionables(target_type.subsystems())

  def _register_target_macro_factory_alias(self, alias, target_macro_factory):
    if alias in self._target_macro_factory_by_alias:
      logger.debug('TargetMacro alias {} has already been registered. Overwriting!'.format(alias))

    self._target_macro_factory_by_alias[alias] = target_macro_factory
    for target_type in target_macro_factory.target_types:
      self.register_optionables(target_type.subsystems())

  def _register_exposed_object(self, alias, obj):
    if alias in self._exposed_object_by_alias:
      logger.debug('Object alias {} has already been registered. Overwriting!'.format(alias))

    self._exposed_object_by_alias[alias] = obj
    # obj doesn't implement any common base class, so we have to test for this attr.
    if hasattr(obj, 'subsystems'):
      self.register_optionables(obj.subsystems())

  def _register_exposed_context_aware_object_factory(self, alias, context_aware_object_factory):
    if alias in self._exposed_context_aware_object_factory_by_alias:
      logger.debug('This context aware object factory alias {} has already been registered. '
                   'Overwriting!'.format(alias))

    self._exposed_context_aware_object_factory_by_alias[alias] = context_aware_object_factory

  @deprecated('1.15.0.dev1', hint_message='Use self.register_optionables().')
  def register_subsystems(self, subsystems):
    return self.register_optionables(subsystems)

  def register_optionables(self, optionables):
    """Registers the given subsystem types.

    :param optionables: The Optionable types to register.
    :type optionables: :class:`collections.Iterable` containing
                       :class:`pants.option.optionable.Optionable` subclasses.
    """
    if not isinstance(optionables, Iterable):
      raise TypeError('The optionables must be an iterable, given {}'.format(optionables))
    optionables = tuple(optionables)
    if not optionables:
      return

    invalid_optionables = [s
                           for s in optionables
                           if not isinstance(s, type) or not issubclass(s, Optionable)]
    if invalid_optionables:
      raise TypeError('The following items from the given optionables are not Optionable '
                      'subclasses:\n\t{}'.format('\n\t'.join(str(i) for i in invalid_optionables)))

    self._optionables.update(optionables)

  def optionables(self):
    """Returns the registered Optionable types.

    :rtype set
    """
    return self._optionables

  @deprecated('1.15.0.dev1', hint_message='Use self.optionables().')
  def subsystems(self):
    """Returns the registered Subsystem types.

    :rtype set
    """
    return {o for o in self._optionables if issubclass(o, Subsystem)}

  def register_rules(self, rules):
    """Registers the given rules.

    param rules: The rules to register.
    :type rules: :class:`collections.Iterable` containing
                 :class:`pants.engine.rules.Rule` instances.
    """
    if not isinstance(rules, Iterable):
      raise TypeError('The rules must be an iterable, given {!r}'.format(rules))

    # "Index" the rules to normalize them and expand their dependencies.
    indexed_rules = RuleIndex.create(rules).normalized_rules()

    # Store the rules and record their dependency Optionables.
    self._rules.update(indexed_rules)
    dependency_optionables = {do
                              for rule in indexed_rules
                              for do in rule.dependency_optionables
                              if rule.dependency_optionables}
    self.register_optionables(dependency_optionables)

  def rules(self):
    """Returns the registered rules.

    :rtype list
    """
    return list(self._rules)

  @memoized_method
  def _get_addressable_factory(self, target_type, alias):
    return TargetAddressable.factory(target_type=target_type, alias=alias)

  def initialize_parse_state(self, build_file):
    """Creates a fresh parse state for the given build file.

    :param build_file: The BUILD file to set up a new ParseState for.
    :type build_file: :class:`pants.base.build_file.BuildFile`
    :returns: A fresh ParseState for parsing the given `build_file` with.
    :rtype: :class:`BuildConfiguration.ParseState`
    """
    # TODO(John Sirois): Introduce a factory method to seal the BuildConfiguration and add a check
    # there that all anonymous types are covered by context aware object factories that are
    # Macro instances.  Without this, we could have non-Macro context aware object factories being
    # asked to be a BuildFileTargetFactory when they are not (in SourceRoot registration context).
    # See: https://github.com/pantsbuild/pants/issues/2125
    type_aliases = self._exposed_object_by_alias.copy()
    parse_context = ParseContext(rel_path=build_file.spec_path, type_aliases=type_aliases)

    def create_call_proxy(tgt_type, tgt_alias=None):
      def registration_callback(address, addressable):
        parse_context._storage.add(addressable, name=address.target_name)
      addressable_factory = self._get_addressable_factory(tgt_type, tgt_alias)
      return AddressableCallProxy(addressable_factory=addressable_factory,
                                  build_file=build_file,
                                  registration_callback=registration_callback)

    # Expose all aliased Target types.
    for alias, target_type in self._target_by_alias.items():
      proxy = create_call_proxy(target_type, alias)
      type_aliases[alias] = proxy

    # Expose aliases for exposed objects and targets in the BUILD file.
    parse_globals = type_aliases.copy()

    # Now its safe to add mappings from both the directly exposed and macro-created target types to
    # their call proxies for context awares and macros to use to manufacture targets by type
    # instead of by alias.
    for alias, target_type in self._target_by_alias.items():
      proxy = type_aliases[alias]
      type_aliases[target_type] = proxy

    for target_macro_factory in self._target_macro_factory_by_alias.values():
      for target_type in target_macro_factory.target_types:
        proxy = create_call_proxy(target_type)
        type_aliases[target_type] = proxy

    for alias, object_factory in self._exposed_context_aware_object_factory_by_alias.items():
      parse_globals[alias] = object_factory(parse_context)

    for alias, target_macro_factory in self._target_macro_factory_by_alias.items():
      parse_globals[alias] = target_macro_factory.target_macro(parse_context)

    return self.ParseState(parse_context, parse_globals)
