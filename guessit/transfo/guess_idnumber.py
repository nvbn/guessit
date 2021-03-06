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
from guessit.transfo import SingleNodeGuesser
from guessit.patterns.properties import container
from guessit import Guess
import re
import logging

log = logging.getLogger(__name__)


def guess_properties(string):
    found = container.find_properties(string)
    if found:
        prop, span = found[0]
        guess = Guess(confidence=prop.confidence)
        guess[prop.name] = prop.canonical_form
        return guess, span
    return None, None

_idnum = re.compile(r'(?P<idNumber>[a-zA-Z0-9-]{20,})') # 1.0, (0, 0))


def guess_idnumber(string):
    match = _idnum.search(string)
    if match is not None:
        result = match.groupdict()
        switch_count = 0
        DIGIT = 0
        LETTER = 1
        OTHER = 2
        last = LETTER
        for c in result['idNumber']:
            if c in '0123456789':
                ci = DIGIT
            elif c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ':
                ci = LETTER
            else:
                ci = OTHER

            if ci != last:
                switch_count += 1

            last = ci

        switch_ratio = float(switch_count) / len(result['idNumber'])

        # only return the result as probable if we alternate often between
        # char type (more likely for hash values than for common words)
        if switch_ratio > 0.4:
            return result, match.span()

    return None, None


priority = -180


def process(mtree):
    SingleNodeGuesser(guess_idnumber, 0.4, log).process(mtree)
