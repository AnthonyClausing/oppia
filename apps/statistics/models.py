# coding: utf-8
#
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Models for Oppia statistics."""

__author__ = 'Sean Lip'

import collections
import utils

from apps.exploration.models import Exploration

from google.appengine.ext import ndb


STATS_ENUMS = utils.create_enum(
    'exploration_visited', 'rule_hit', 'exploration_completed',
    'feedback_submitted', 'state_hit')


def create_rule_name(rule):
    name = rule.name
    for key in rule.inputs.keys():
        left_paren = name.index('(')
        name = name[0:left_paren] + name[left_paren:].replace(key, str(rule.inputs[key]))
    return name


def get_event_key(event_name, key):
        if event_name == STATS_ENUMS.exploration_visited:
            return 'e.%s' % key
        if event_name == STATS_ENUMS.rule_hit:
            return 'default.%s' % key
        if event_name == STATS_ENUMS.exploration_completed:
            return 'c.%s' % key
        if event_name == STATS_ENUMS.feedback_submitted:
            return 'f.%s' % key
        if event_name == STATS_ENUMS.state_hit:
            return 's.%s' % key



class EventHandler(object):
    """Records events."""

    @classmethod
    def _record_event(cls, event_name, key, extra_info=''):
        """Updates statistics based on recorded events."""

        event_key = get_event_key(event_name, key)

        if event_name == STATS_ENUMS.exploration_visited:
            cls._inc(event_key)
        if event_name == STATS_ENUMS.rule_hit:
            cls._add(event_key, unicode(extra_info))
        if event_name == STATS_ENUMS.exploration_completed:
            cls._inc(event_key)
        if event_name == STATS_ENUMS.feedback_submitted:
            cls._add(event_key, unicode(extra_info))
        if event_name == STATS_ENUMS.state_hit:
            cls._inc(event_key)

    @classmethod
    def record_rule_hit(cls, exploration_id, state_id, rule, extra_info=''):
        """Records an event when an answer triggers the default rule."""
        cls._record_event(
            STATS_ENUMS.rule_hit, '%s.%s.%s' % (exploration_id, state_id, create_rule_name(rule)),
            extra_info)

    @classmethod
    def record_exploration_visited(cls, exploration_id):
        """Records an event when an exploration is first loaded."""
        cls._record_event(STATS_ENUMS.exploration_visited, exploration_id)

    @classmethod
    def record_exploration_completed(cls, exploration_id):
        """Records an event when an exploration is completed."""
        cls._record_event(STATS_ENUMS.exploration_completed, exploration_id)

    @classmethod
    def record_feedback_submitted(cls, url, feedback):
        """Records an event where feedback was submitted via the web UI."""
        cls._record_event(
            STATS_ENUMS.feedback_submitted, url, extra_info=feedback
        )

    @classmethod
    def record_state_hit(cls, exploration_id, state_id):
        """Record an event when a state is loaded."""
        cls._record_event(STATS_ENUMS.state_hit, '%s.%s' % (exploration_id, state_id))

    @classmethod
    def _inc(cls, event_key):
        """Increments the counter corresponding to an event key."""
        counter = Counter.get_or_insert(event_key, name=event_key)
        if not counter:
            counter = Counter(id=event_key, name=event_key)
        counter.value += 1
        counter.put()

    @classmethod
    def _add(cls, event_key, value):
        """Adds to the list corresponding to an event key."""
        journal = Journal.get_or_insert(event_key, name=event_key)
        if not journal:
            journal = Journal(id=event_key, name=event_key)
        journal.values.append(value)
        journal.put()


class Counter(ndb.Model):
    """An integer-valued counter."""
    # The name of the property.
    name = ndb.StringProperty()
    # The value of the property.
    value = ndb.IntegerProperty(default=0)
    # When this counter was first created.
    created = ndb.DateTimeProperty(auto_now_add=True)
    # When this counter was last incremented.
    last_updated = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def get_value_by_id(cls, key):
        counter = Counter.get_by_id(key)
        if not counter:
            return 0
        else:
            return counter.value
    


class Journal(ndb.Model):
    """A list of values."""
    # The name of the list
    name = ndb.StringProperty()
    # The list of values
    values = ndb.StringProperty(repeated=True)
    # When this counter was first created.
    created = ndb.DateTimeProperty(auto_now_add=True)
    # When this counter was last updated.
    last_updated = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def get_value_count_by_id(cls, key):
        journal = Journal.get_by_id(key)
        if journal:
           return len(journal.values)
        else:
           return 0


class Statistics(object):
    """Retrieves statistics to display in the views."""

    @classmethod
    def get_exploration_stats(cls, event_name, exploration_id):
        """Retrieves statistics for the given event name and exploration id."""

        if event_name == STATS_ENUMS.exploration_visited:
            event_key = get_event_key(event_name, exploration_id)
            counter = Counter.get_by_id(event_key)
            if not counter:
                return 0
            return counter.value

        if event_name == STATS_ENUMS.exploration_completed:
            event_key = get_event_key(event_name, exploration_id)
            counter = Counter.get_by_id(event_key)
            if not counter:
                return 0
            return counter.value

        if event_name == STATS_ENUMS.rule_hit:
            result = {}

            exploration = Exploration.get(exploration_id)
            for state_key in exploration.states:
                state = state_key.get()
                result[state.id] = {
                    'name': state.name,
                    'rules': {}
                }
                for handler in state.widget.handlers:
                    for rule in handler.rules:
                        rule_name = create_rule_name(rule)
                        event_key = get_event_key(event_name, (exploration_id, state.id, rule_name))

                        journal = Journal.get_by_id(event_key)

                        if journal:
                            top_ten = collections.Counter(
                                journal.values).most_common(10)
                        else:
                            top_ten = []

                        result[state.id]['rules'][rule_name] = {
                            'answers': top_ten,
                        }

            return result

        if event_name == STATS_ENUMS.state_hit:
            result = {}

            exploration = Exploration.get(exploration_id)
            for state_key in exploration.states:
                state = state_key.get()
                event_key = get_event_key(event_name, (exploration_id, state.id))

                counter = Counter.get_by_id(event_key)
                if not counter:
                    count = 0
                else:
                    count = counter.value

                result[state.id] = {
                    'name': state.name,
                    'count': count,
                }
            return result

    @classmethod
    def get_top_ten_improvable_states(cls, exploration_ids):
        ranked_states = [] 
        for exp in exploration_ids:
            exploration = Exploration.get(exp)
            for state_db_key in exploration.states:
                state = state_db_key.get()
                state_key = '%s.%s' % (exp, state.id)

                # Get count of how many times state was hit
                event_key = get_event_key(STATS_ENUMS.state_hit, state_key)
                all_count = Counter.get_value_by_id(event_key)
                if all_count == 0:
                    continue

                completed_count = 0
                event_key = get_event_key(STATS_ENUMS.rule_hit, '%s.Default' % state_key)
                default_count = Journal.get_value_count_by_id(event_key)
                for handler in state.widget.handlers:
                    for rule in handler.rules:
                        rule_name = create_rule_name(rule)
                        event_key = get_event_key(STATS_ENUMS.rule_hit, '%s.%s' % (state_key, rule_name))
                        completed_count += Journal.get_value_count_by_id(event_key)
                incomplete_count = all_count - completed_count
                if (float(default_count) / all_count > .2):
                    if (float(incomplete_count) / all_count > .2):
                        if (default_count > incomplete_count):
                            state_rank = default_count
                            improve_type = 'default'
                        else:
                            state_rank = incomplete_count
                            improve_type = 'incomplete'
                    else:
                        state_rank = default_count
                        improve_type = 'default'
                elif (float(incomplete_count) / all_count > .2):
                    state_rank = incomplete_count
                    improve_type = 'incomplete'
                else:
                    state_rank = 0
                    improve_type = ''
                ranked_states.append({'exp_id': exp, 'state_id': state.id, 'rank': state_rank, 'type': improve_type})
        problem_states = [i for i in ranked_states if i['rank'] != 0]
        return sorted(problem_states, key=lambda state: state['rank'])[:10]
