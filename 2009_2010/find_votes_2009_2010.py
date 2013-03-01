#!/usr/bin/env python

import os
import sys
import logging
import json

logger = logging.getLogger("senate")
logger.setLevel("INFO")
logger.addHandler(logging.StreamHandler())
logger.addHandler(logging.FileHandler('last_run_status.txt'))

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

def sample_test(lines, line, index):
    return True

def getblocksByTests(lines, begin_test, end_test):
    """ Provide two functions to test, if these return true, then a
    chunk is matched.

    Each test function takes as arguments lines, line, and index, where
    lines is the whole text, line is the current line being iterated,
    and index is the index to that line in the text.

        begin_test - lines are all of the lines in the whole text

        end_test - lines are only the lines containing the first matched
        line, and all lines after. That is, lines sliced at the index of
        begin_test's line match index

    Test functions may be however complex.

    The function returns a list of chunks that are matched.

    """

    match_indexes = []

    i = 0
    for line in lines:

        if begin_test(lines, line, i):
            # Within block
            j = 0
            inner = lines[:][i::]
            for _line in inner:
                if end_test(inner, _line, j):
                    match_indexes.append((i - 1, i + j + 1))
                    j = 0
                    break
                j += 1

        i += 1

    chunks = [lines[a:b] for a, b in match_indexes]
    return chunks

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

find_bill_title = re.compile(r'([HS]\.F\. No\. \d+)')
def process_vote_chunk(chunk):
    bill_title        = False
    affirmative_names = False
    negative_names    = False

    pass_status = [a for a in chunk if 'So the bill' in a][0]

    for _l in chunk:
        if 'H.F. No.' in _l or 'S.F. No.' in _l:
            bill_title_line = _l
            break

    if bill_title_line:
        try:
            bill_title = find_bill_title.search(bill_title_line).groups()[0]
        except:
            pass

    aff_and_neg = getblock( chunk
                          , 'Those who voted in the affirmative'
                          , 'Those who voted in the negative'
                          )
    if aff_and_neg:
        affirmatives = getblock( chunk
                               , 'Those who voted in the affirmative'
                               , 'Those who voted in the negative'
                               )
        negatives = getblock( chunk
                            , 'Those who voted in the negative'
                            , 'So the bill'
                            )
    else:
        affirmatives = getblock( chunk
                               , 'Those who voted in the affirmative'
                               , 'So the bill'
                               )
        negatives = False

    affs = affirmatives[1:len(affirmatives) - 1]
    affirmative_names = [ a for a in sum([splitter(a) for a in affs], [])
                          if a.strip() ]

    if negatives:
        neg = negatives[1:len(negatives) - 1]
        negative_names = [ a for a in sum([splitter(a) for a in neg], [])
                           if a.strip() ]
        negative_names = sorted(negative_names)

    result = { 'affirmatives': sorted(affirmative_names)
             , 'negatives': negative_names
             , 'title': bill_title
             , 'status': pass_status
             }

    return result

def find_votes(lines):
    def begin_test(lines, line, index):
        """ Two formats to the beginning of a vote on a bill.
             * bill is read with description included
             * bill is read without description
        """
        first_possibility = False

        if index > 10:
            next_ten = lines[index:index+10]

            hf_or_sf        = ('S.F. No.' in line) or ('H.F. No.' in line)
            was_read        = 'was read' in line
            placed_on       = 'placed on' in line

            bill_vote_begin = all([hf_or_sf, was_read, placed_on])

            if bill_vote_begin:
                a = 'question was taken on'
                b = 'roll was called'
                c = 'Those who voted in'
                _a, _b, _c = False, False, False
                for _l in next_ten:
                    if a in _l:
                        _a = True
                    if b in _l:
                        _b = True
                    if c in _l:
                        _c = True
                if all([_a, _b, _c]):
                    first_possibility = False

        second_possibility = False

        a_bill_for = ": A bill for an act relating to" in line
        if a_bill_for:
            a = "Was read the third time"
            b = "The question was taken"
            c = "The roll was called"
            d = "Those who voted"
            _a, _b, _c, _d = False, False, False, False

            for _l in lines[index+1::]:
                if ('H.F. No.' in _l) or ('S.F. No.' in _l):
                    second_possibility = False
                    break
                else:
                    if a in _l:
                        _a = True
                    if b in _l and _a:
                        _b = True
                    if c in _l and _b and _a:
                        _c = True
                    if d in _l and _c and _b and _a:
                        _d = True
            if all([_a, _b, _c, _d]):
                second_possibility = True

        return first_possibility or second_possibility

    def end_test(inner, line, index):
        if 'So the bill' in line:
            return True
        return False

    vote_chunks = getblocksByTests(lines, begin_test, end_test)

    if len(vote_chunks) == 0:
        return False

    processed_votes = map(process_vote_chunk, vote_chunks)

    return processed_votes

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

    no_page_breaks = lambda x: not x.startswith("")
    with open(filename) as F:
        data = filter(no_page_breaks, F.read().splitlines())

    _date_info = parse_date(data[0:3])

    if _date_info:
        logger.info("%s - DATE: %s" % (filename, str(bool(_date_info))))
    else:
        logger.warning( "%s - ROLL: ERROR" % filename)

    data = map( lambda x: x.strip()
              , data
              )

    names = call_of_the_senate(data)

    if names:
        logger.info("%s - ROLL: %s" % (filename, str(bool(names))))
    else:
        logger.warning( "%s - ROLL: ERROR" % filename)

    # TODO: first readings of bills could be possible
    # The following bill(s) was/were read for the first time.

    votes = find_votes(data)

    if votes:
        logger.info("%s - VOTES: %s" % (filename, str(bool(votes))))
    else:
        logger.warning( "%s - VOTES: ERROR" % filename)

    journal = { 'role_call': names
              , 'bill_votes': votes
              , 'filename': filename
              , 'date': _date_info
              }

    with open(filename + '.json', 'w') as F:
        print >> F, json.dumps(journal, indent=4).encode('utf-8')

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
