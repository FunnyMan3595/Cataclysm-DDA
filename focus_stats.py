#!/usr/bin/python
# -*- coding: utf-8 -*-

import numpy, re
from collections import defaultdict

BASE = None
TRAINED = "Trained"
MORALE = "Morale"

class TypeHandler(object):
    def __init__(self, parse_re, parse_types, format_string, names):
        self.parse_re = parse_re
        self.parse_types = parse_types
        self.format_string = format_string
        self.names = names

    def parse(self, data):
        try:
            groups = self.parse_re.match(data).groups()
        except Exception:
            print data
            raise
        return tuple(self.parse_types[i](groups[i]) for i in range(len(groups)))

    def format(self, data):
        return self.format_string % data


handlers = {
    BASE: TypeHandler(re.compile(r"^\(([0-9]*)->([0-9]*)\) ([^ ]*) (.*)$"),
                      (int,int,str,str), "", ()),

    TRAINED: TypeHandler(re.compile(r"^([^+]*) \+([0-9]*)$"),
                         (str, int), "%s %+d", ("skill", "xp")),
    MORALE: TypeHandler(re.compile(r"^([0-9]*): ([+-][0-9]*)%$"),
                        (int, int), "%d: +%d%%", ("morale", "chance"))
}

class FocusChange(object):
    handler = property(lambda self: handlers[self.type])

    def __init__(self, pre, post, type_, format_args):
        self.pre = pre
        self.post = post
        self.type = type_
        self.format_args = format_args

    def __str__(self):
        return "(%d->%d) %s %s" % (self.pre, self.post, self.type,
                                   self.handler.format(self.format_args))

    def __repr__(self):
        return "FocusChange%r" % ((self.pre, self.post, self.type,
                                   self.handler.format_string,
                                   self.format_args),)

    def __getattr__(self, attr):
        if attr in self.handler.names:
            return self.format_args[self.handler.names.index(attr)]

        print attr, self.handler.names

        raise AttributeError(attr)

    def change(self):
        return self.post - self.pre

    def __nonzero__(self):
        return bool(self.change())

    @staticmethod
    def build_from(log_line):
        pre, post, type, extra = handlers[BASE].parse(log_line)

        format_args = handlers[type].parse(extra)

        return FocusChange(pre, post, type, format_args)


def only(type_):
    def filterfunc(change):
        return change.type == type_
    return filterfunc

import os.path
for file in os.listdir("focus_logs"):
    if not file.endswith(".out"):
        changes = []
        with open(os.path.join("focus_logs", file)) as infile:
            lines = infile.readlines()
            for line in lines:
                changes.append(FocusChange.build_from(line))

        with open(os.path.join("focus_logs", file + ".out"), "w") as outfile:
            outfile.write("Total changes: %d\n" % len(changes))
            outfile.write("Nonzero changes: %d\n" % len(filter(None, changes)))

            values = defaultdict(int)
            for change in changes:
                values[change.change()] += 1

            outfile.write("Change amounts: %r\n" % dict(values))
            outfile.write("Net change: %d\n" % sum(c.change() for c in changes))

            outfile.write("\n")

            trained = filter(only(TRAINED), changes)
            if trained:
                all_xp = sum(t.xp for t in trained)
                avg_focus = numpy.mean(tuple(t.pre for t in trained))
                est_raw_xp = all_xp * (100.0 / avg_focus)

                outfile.write("Total XP trained: %d\n" % all_xp)
                outfile.write("Average focus while training: %0.1f\n" % avg_focus)
                outfile.write("Raw XP trained (est.): %0.1f\n" % est_raw_xp)

                by_skill = defaultdict(list)

                for t in trained:
                    by_skill[t.skill].append(t)

                skills = sorted(by_skill.keys())

                if len(skills) > 1:
                    outfile.write("\n");
                    outfile.write("skill     : count @    avg =    raw *  focus = total\n")

                    for skill in skills:
                        mine = by_skill[skill]
                        count = len(mine)

                        my_xp = sum(t.xp for t in mine)
                        my_focus = numpy.mean(tuple(t.pre for t in mine))
                        my_raw_xp = my_xp * (100.0 / my_focus)

                        my_avg_raw = my_raw_xp / count

                        outfile.write("{:10s}: {:5d} @ {:6.1f} = {:6.1f} * {:6.1f} = {:4d}\n".format(skill, count, my_avg_raw, my_raw_xp, my_focus, my_xp))
                else:
                    outfile.write("Only skill trained: %s\n" % skills[0])
            else:
                outfile.write("No skill training logged.\n")

            outfile.write("\n")

            morale = filter(only(MORALE), changes)
            if not morale:
                outfile.write("No time increments logged.\n")
                continue

            minutes = len(morale)
            high_morale = max(m.morale for m in morale)
            low_morale = min(m.morale for m in morale)
            avg_morale = numpy.mean(tuple(m.morale for m in morale))
            avg_focus = numpy.mean(tuple(m.pre for m in morale))
            avg_gain_theory = numpy.mean(tuple(m.chance for m in morale))
            avg_gain = sum(m.change() for m in morale) / float(len(morale))

            outfile.write("Minutes passed: %d\n" % minutes)
            outfile.write("Maximum morale: %d\n" % high_morale)
            outfile.write("Minimum morale: %d\n" % low_morale)
            outfile.write("Average morale: %d\n" % avg_morale)
            outfile.write("Average focus: %d\n" % avg_focus)
            outfile.write("Average focus gain (theory): % 3d.00%%\n" % avg_gain_theory)
            outfile.write("Average focus gain (actual): % 6.2f%%\n" % (avg_gain * 100))
