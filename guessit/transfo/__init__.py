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
from guessit import base_text_type, Guess
from guessit.patterns.synonyms import get_synonym
from guessit.patterns.numeral import parse_numeral
from guessit.textutils import clean_string
import logging

log = logging.getLogger(__name__)


class TransfoException(Exception):
    def __init__(self, transformer, message):

        # Call the base class constructor with the parameters it needs
        Exception.__init__(self, message)

        self.transformer = transformer


class _TransfoManager(object):
    _transformers = None
    _transformers_dict = {}

    _transformer_names = ('guessit.transfo.split_path_components',
        'guessit.transfo.guess_filetype',
        'guessit.transfo.split_explicit_groups',
        'guessit.transfo.guess_date',
        'guessit.transfo.guess_website',
        'guessit.transfo.guess_release_group',
        'guessit.transfo.guess_properties',
        'guessit.transfo.guess_language',
        'guessit.transfo.guess_video_rexps',
        'guessit.transfo.guess_episodes_rexps',
        'guessit.transfo.guess_weak_episodes_rexps',
        'guessit.transfo.guess_bonus_features',
        'guessit.transfo.guess_year',
        'guessit.transfo.guess_country',
        'guessit.transfo.guess_idnumber',
        'guessit.transfo.split_on_dash',
        'guessit.transfo.guess_episode_info_from_position',
        'guessit.transfo.guess_movie_title_from_position',
        'guessit.transfo.post_process'
        )

    def get_transformers(self):
        """Retrieves registered transformer modules
        """
        if self._transformers is None:
            self.reload_transformers()
        return self._transformers

    def reload_transformers(self):
        """Load transformers module into the manager
        """
        self._transformers = self._load_transformers()
        for transformer in self._transformers:
            self._transformers_dict[transformer.__name__] = transformer
        return self._transformers

    def get_transformer(self, name):
        return self._transformers_dict.get(name)

    def _load_transformers(self):
        transformers = []
        for transfo_name in self._transformer_names:
            transformer = __import__(transfo_name,
                     globals=globals(), locals=locals(),
                     fromlist=['process'], level=0)
            transformers.append(transformer)
        self._order_transformers(transformers)
        return transformers

    def _order_transformers(self, transformers):
        """Order the loaded transformers

        It should follow those rules
           - website before language (eg: tvu.org.ru vs russian)
           - language before episodes_rexps
           - properties before language (eg: he-aac vs hebrew)
           - release_group before properties (eg: XviD-?? vs xvid)
        """
        transformers.sort(key=lambda transfo: -transfo.priority)

transfo_manager = _TransfoManager()


def found_property(node, name, confidence):
    node.guess = Guess({name: node.clean_value}, confidence=confidence)
    log.debug('Found with confidence %.2f: %s' % (confidence, node.guess))


def format_guess(guess):
    """Format all the found values to their natural type.
    For instance, a year would be stored as an int value, etc...

    Note that this modifies the dictionary given as input.
    """
    for prop, value in guess.items():
        if prop in ('season', 'episodeNumber', 'year', 'cdNumber',
                    'cdNumberTotal', 'bonusNumber', 'filmNumber'):
            guess[prop] = parse_numeral(guess[prop])
        elif isinstance(value, base_text_type):
            if prop in ('edition',):
                value = clean_string(value)
            guess[prop] = get_synonym(value).replace('\\', '')

    return guess


def find_and_split_node(node, strategy, skip_nodes, logger, partial_span=None):
    value = None
    if partial_span:
        value = node.value[partial_span[0]:partial_span[1]]
    else:
        value = node.value
    string = ' %s ' % value  # add sentinels
    for matcher, confidence, args, kwargs in strategy:
        all_args = [string]
        if getattr(matcher, 'use_node', False):
            all_args.append(node)
        if args:
            all_args.append(args)

        if kwargs:
            match = matcher(*all_args, **kwargs)
        else:
            match = matcher(*all_args)

        if match:
            if not isinstance(match, Guess):
                result, span = match
            else:
                result, span = match, match.metadata().span

            if result:
                # readjust span to compensate for sentinels
                span = (span[0] - 1, span[1] - 1)

                # readjust span to compensate for partial_span
                if partial_span:
                    span = (span[0] + partial_span[0], span[1] + partial_span[0])

                partition_spans = None
                for skip_node in skip_nodes:
                    if skip_node.parent.node_idx == node.node_idx[:len(skip_node.parent.node_idx)] and\
                        skip_node.span == span:
                        partition_spans = node.get_partition_spans(skip_node.span)
                        partition_spans.remove(skip_node.span)
                        break

                if not partition_spans:
                    # restore sentinels compensation

                    guess = None
                    if isinstance(result, Guess):
                        if confidence is None:
                            confidence = result.confidence()
                        guess = result
                    else:
                        if confidence is None:
                            confidence = 1.0
                        guess = Guess(result, confidence=confidence, input=string, span=span)

                    guess = format_guess(guess)
                    msg = 'Found with confidence %.2f: %s' % (confidence, guess)
                    (logger or log).debug(msg)

                    node.partition(span)
                    absolute_span = (span[0] + node.offset, span[1] + node.offset)
                    for child in node.children:
                        if child.span == absolute_span:
                            child.guess = guess
                        else:
                            find_and_split_node(child, strategy, skip_nodes, logger)
                else:
                    for partition_span in partition_spans:
                        find_and_split_node(node, strategy, skip_nodes, logger, partition_span)


class SingleNodeGuesser(object):
    def __init__(self, guess_func, confidence, logger, *args, **kwargs):
        self.guess_func = guess_func
        self.confidence = confidence
        self.logger = logger
        self.skip_nodes = kwargs.pop('skip_nodes', [])
        self.args = args
        self.kwargs = kwargs

    def process(self, mtree):
        # strategy is a list of pairs (guesser, confidence)
        # - if the guesser returns a guessit.Guess and confidence is specified,
        #   it will override it, otherwise it will leave the guess confidence
        # - if the guesser returns a simple dict as a guess and confidence is
        #   specified, it will use it, or 1.0 otherwise
        strategy = [(self.guess_func, self.confidence, self.args, self.kwargs)]

        for node in mtree.unidentified_leaves():
            find_and_split_node(node, strategy, self.skip_nodes, self.logger)
