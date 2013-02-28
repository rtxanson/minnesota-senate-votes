#!/usr/bin/env python

import os
import sys
import logging
import json

logger = logging.getLogger("senate")
logger.setLevel("INFO")
logger.addHandler(logging.StreamHandler())

DEBUG = True

def getblock(lines, start_str, end_str):
    begin_no = False
    end_no = False

    i = 0
    for line in lines:
        if line.find(start_str) > -1:
            begin_no = i
            break
        i += 1

    if begin_no:
        for line in lines[begin_no::]:
            if line.find(end_str) > -1 and not end_no:
                end_no = i + 1
            i += 1

        return lines[begin_no:end_no]

    return False

def chunkby(lines, chunk_str=False, regex=False):
    if chunk_str:
        match = lambda x: x.find(chunk_str) > -1
    elif regex:
        _matcher = re.compile(regex).match
        match = lambda x: _matcher(x) is not None

    #chunker = re.compile('^(\w*)?S\.F\. No\. \d*')
    cur_chunk = []
    for line in lines[1::]:
        if match(line):
            if len(cur_chunk) > 0:
                yield cur_chunk
            cur_chunk = []
            cur_chunk.append(line)
        else:
            cur_chunk.append(line)


def session_date(lines):
    return lines

import re
splitter = re.compile('\s{2,}').split

def call_of_the_senate(lines):
    start = "The Senate met at "
    end   = " declared a quorum present."

    call_of_senate = getblock( lines
                             , start
                             , end
                             )

    if not call_of_senate:
        return False

    roll = getblock( call_of_senate
                   , "The roll was called"
                   , "quorum"
                   )

    # TODO: move elsewhere so filename is avail

    if not roll:
        return False

    senator_list = roll[1:len(roll) - 1]

    names = sorted([ a for a in sum([splitter(a) for a in senator_list], [])
                     if a.strip() ])

    _n_count = len(names)

    return names

def process_vote_chunk(chunk):
    affirmative_names = False
    negative_names    = False

    aff_and_neg = getblock( chunk
                          , 'Those who voted in the affirmative'
                          , 'Those who voted in the negative'
                          )
    if aff_and_neg:
        negatives = getblock( chunk
                            , 'Those who voted in the negative'
                            , 'So the bill'
                            )
        affirmatives = aff_and_neg
    else:
        negatives = False

    affirmatives = getblock( chunk
                           , 'Those who voted in the affirmative'
                           , 'So the bill'
                           )

    affs = affirmatives[1:len(affirmatives) - 1]
    affirmative_names = sorted([ a for a in sum([splitter(a) for a in affs], [])
                                 if a.strip() ])

    if negatives:
        neg = negatives[1:len(negatives) - 1]
        negative_names = sorted([ a for a in sum([splitter(a) for a in neg], [])
                                  if a.strip() ])
    result = { 'affirmatives': affirmative_names
             , 'negatives': negative_names
             }

    return result

def find_votes(lines):
    start = "INTRODUCTION AND FIRST READING OF SENATE BILLS"
    end = "REPORTS OF COMMITTEES"
    votes = getblock( lines
                    , start
                    , end
                    )
    if not votes:
        return False

    vote_chunks = chunkby( votes
                         , ": A bill for an act relating to"
                         )

    vote_chunks = list(vote_chunks)
    processed = []
    for c in vote_chunks:
        has_vote = False
        for l in c:
            if 'roll was called,' in l:
                has_vote = True

        if has_vote:
            _votes = process_vote_chunk(c)
            _votes['title'] = c[0].strip().partition(':')[0]
            processed.append(_votes)

    return processed

def parse_date(lines):
    import datetime
    strp = datetime.datetime.strptime

    date_line = False
    splitter = re.compile('\s{2,}').split
    for d in lines:
        if 'DAY' in d:
            date_line = d

    if not date_line:
        return False

    _x = splitter(date_line)
    day = _x[0]
    date = _x[1]

    if day:
        day = day.replace(']', '').lower()

    try:
        formatted = strp(date, '%A, %B %d, %Y').isoformat()
    except ValueError:
        formatted = False

    result = { 'date_utc': formatted
             , 'date_string': date
             , 'session_day': day
             }

    return result

def main(filename):
    _date = False
    _day  = False

    no_page_breaks = lambda x: not x.startswith("")
    with open(filename) as F:
        data = filter(no_page_breaks, F.read().splitlines())

    _date_info = parse_date(data[0:3])

    if _date_info:
        logger.info("%s - DATE: %s" % (filename, str(bool(_date_info))))
    else:
        logger.warning( "%s - ROLL: ERROR" % filename)

    names = call_of_the_senate(data)

    if names:
        logger.info("%s - ROLL: %s" % (filename, str(bool(names))))
    else:
        logger.warning( "%s - ROLL: ERROR" % filename)

    votes = find_votes(data)

    if votes:
        logger.info("%s - VOTES: %s" % (filename, str(bool(votes))))
    else:
        logger.warning( "%s - VOTES: ERROR" % filename)

    journal = { 'role_call': names
              , 'votes': votes
              , 'filename': filename
              , 'date': _date_info
              }

    with open(filename + '.json', 'w') as F:
        print >> F, json.dumps(journal, indent=4)
    
    return

if __name__ == "__main__":
    pdf_file = sys.argv[1]

    try:
        main(pdf_file)
    except Exception, e:
        import traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, limit=10, file=sys.stdout)
        logger.error(e)
        logger.error(" Error with: %s" % pdf_file)

    sys.exit()


# vim: set ts=4 sw=4 tw=72 syntax=python expandtab:
