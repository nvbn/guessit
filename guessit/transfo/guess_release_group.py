#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# GuessIt - A library for guessing information from filenames
# Copyright (c) 2013 Nicolas Wack <wackou@gmail.com>
#
# GuessIt is free software; you can redistribute it and/or modify it under
# the terms of the Lesser GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# GuessIt is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Lesser GNU General Public License for more details.
#
# You should have received a copy of the Lesser GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import unicode_literals
from guessit.transfo import SingleNodeGuesser, format_guess
from guessit.patterns.properties import container
import logging
from guessit.patterns.containers import PropertiesContainer
from guessit.patterns import sep
from guessit.guess import Guess

log = logging.getLogger(__name__)

groups_container = PropertiesContainer()

_allowed_groupname_pattern = r'[\w@#€£$&]'


def _is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

_forbidden_groupname_lambda = [lambda elt: elt in ['rip', 'by', 'for', 'par', 'pour', 'bonus'],
                               lambda elt: _is_number(elt),
                               ]

# If the previous property in this list, the match will be considered as safe
# and group name can contain a separator.
previous_safe_properties = ['videoCodec', 'format', 'videoApi', 'audioCodec']


groups_container.sep_replace_char = '-'
groups_container.canonical_from_pattern = False
groups_container.enhance_patterns = True
groups_container.register_property('releaseGroup', None, _allowed_groupname_pattern + '+')
groups_container.register_property('releaseGroup', None, _allowed_groupname_pattern + '+-' + _allowed_groupname_pattern + '+')


def adjust_metadata(md):
    return dict((property_name, container.compute_canonical_form(property_name, value) or value)
                for property_name, value in md.items())


def validate_group_name(guess):
    if guess.metadata().span[1] - guess.metadata().span[0] >= 2:
        val = guess['releaseGroup']

        if '-' in guess['releaseGroup']:
            checked_val = ""
            for elt in val.split('-'):
                forbidden = False
                for forbidden_lambda in _forbidden_groupname_lambda:
                    forbidden = forbidden_lambda(elt.lower())
                    if forbidden:
                        break
                if not forbidden:
                    if checked_val:
                        checked_val += '-'
                    checked_val += elt
                else:
                    break
            val = checked_val
            if not val:
                return False
            guess['releaseGroup'] = val

        forbidden = False
        for forbidden_lambda in _forbidden_groupname_lambda:
            forbidden = forbidden_lambda(val.lower())
            if forbidden:
                break
        if not forbidden:
            return True
    return False


def is_leaf_previous(leaf, node):
    if leaf.span[1] <= node.span[0]:
        for idx in xrange(leaf.span[1], node.span[0]):
            if not leaf.root.value[idx] in sep:
                return False
        return True
    return False


def guess_release_group(string, node):
    found = groups_container.find_properties(string, 'releaseGroup')
    guess = groups_container.as_guess(found, string, validate_group_name, sep_replacement='-')
    if guess:
        explicit_group_idx = node.node_idx[:2]
        explicit_group = node.root.node_at(explicit_group_idx)
        for leaf in explicit_group.leaves_containing(previous_safe_properties):
            if is_leaf_previous(leaf, node):
                if leaf.root.value[leaf.span[1]] == '-':
                    guess.metadata().confidence = 1
                else:
                    guess.metadata().confidence = 0.7
                return guess

        # If previous group last leaf is identified as a safe property,
        # consider the raw value as a groupname
        if len(explicit_group_idx) > 0 and explicit_group_idx[-1] > 0:
            previous_group = explicit_group_idx[:-1] + (explicit_group_idx[-1]-1,)
            previous_node = node.root.node_at(previous_group)
            for leaf in previous_node.leaves_containing(previous_safe_properties):
                if is_leaf_previous(leaf, node):
                    guess = Guess({'releaseGroup': node.clean_value}, confidence=1, input=node.value, span=node.span)
                    if validate_group_name(guess):
                        guess = format_guess(guess)
                        node.guess = guess
                        break

    return None

guess_release_group.use_node = True

supported_properties = groups_container.get_supported_properties()


priority = -190


def process(mtree):
    SingleNodeGuesser(guess_release_group, None, log).process(mtree)
