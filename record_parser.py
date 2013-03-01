#!/usr/bin/env python
"""Record parser. Reads a pdftotext-converted senate record, and outputs JSON.

Usage:
  record_parser.py read <input_file> [options]
  record_parser.py read <input_file> <output_file> [options]
  record_parser.py (-h | --help)

Options:
  -h --help             Show this screen.
  --format=<format>     Output format. [default: JSON]
  --with-resolutions    Output votes on resolutions.
  --with-amendments     Output votes on amendments.
"""


# TODO: first readings of bills could be possible, but maybe already
#       included in some other machine readable dataset online
#
#     "The following bill(s) was/were read for the first time."
#
# TODO: votes on resolutions
# TODO: votes on adoptions of amendments
# TODO: things that committees reccommend
# TODO: adoption of motions
#
# TODO: keyword mentions
#  - all bill titles mentioned (note several formats, individual and list
#    format, No. vs. Nos.)
#  - committee mentions...?

from docopt import docopt
import sys
import logging
import json
import re

logger = logging.getLogger("senate")
logger.setLevel("INFO")
logger.addHandler(logging.StreamHandler())
logger.addHandler(logging.FileHandler('last_run_status.txt'))

# TODO: make this a commandline switch later
DEBUG = True

##
###  Utility functions
##

# These ideally will not need to change much to handle new types of
# records.

# [str], str, str -> [str] or False
def getblock(lines, start_str, end_str):
    """ Find a block of text where the bounding lines contain start_str
        and end_str. Inclusive of bounding lines.
    """
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

# [str], func, func -> [[str]]
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

        >>> def sample_test(lines, line, index):
        >>>     return True

    This function returns a list of chunks that are matched.

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

##
###  Document parsing
##

splitter = re.compile('\s{2,}').split
def parse_vote_name_block(block):
    names = sum([splitter(line) for line in block], [])
    return sorted(filter(lambda a: a.strip(), names))

def call_of_the_senate(lines):
    start = "The Senate met at "
    end   = " declared a quorum present."

    call_of_senate = getblock(lines, start, end)

    if not call_of_senate:
        return False

    roll = getblock(call_of_senate, "The roll was called", "quorum")

    if not roll:
        return False

    senator_list = parse_vote_name_block( roll[1:len(roll) - 1] )

    return senator_list


find_bill_title = re.compile(r'([HS]\.( )?F\. No\. \d+)')
def process_vote_chunk(chunk):
    bill_title        = False
    affirmative_names = []
    negative_names    = []

    pass_status = [a for a in chunk if 'So the bill' in a][0]

    # Look for title line
    for _l in chunk:
        if 'F. No.' in _l:
            bill_title_line = _l
            break

    if bill_title_line:
        try:
            bill_title = find_bill_title.search(bill_title_line).groups()[0]
        except:
            pass

    # TODO: umm, also what about just negatives?
    _vote_aff = 'Those who voted in the affirmative'
    _vote_neg = 'Those who voted in the negative'

    includes_negative = getblock(chunk, _vote_aff, _vote_neg)
    if includes_negative:
        affirmatives = includes_negative
        negatives    = getblock(chunk, _vote_neg, 'So the bill')

        # Pop off the inclusive end block match line
        neg = negatives[1:len(negatives) - 1]
        negative_names = parse_vote_name_block(neg)
    else:
        affirmatives = getblock(chunk, _vote_aff, 'So the bill')
        negatives_names = []

    # Pop off the inclusive end block match line
    affs = affirmatives[1:len(affirmatives) - 1]
    affirmative_names = parse_vote_name_block(affs)

    log_args = ( str(bill_title)
               , len(affirmative_names)
               , len(negative_names)
               )
    logger.info("    %s - yays: %d, nays: %d" % log_args)

    return  { 'affirmatives': affirmative_names
            , 'negatives': negative_names
            , 'title': bill_title
            , 'status': pass_status
            }

def find_votes(lines):
    """ Find bill votes in the whole text, and return a list of vote
    info.
    """

    def begin_test(lines, line, index):
        """ Two formats to the beginning of a vote on a bill.
             * bill is read with description included
             * bill is read without description
        """
        # TODO: 20100515106 l. 14135 - matching a block which is too big
        # and ends in:
        # So the resolution passed and its title was agreed to.
        # However obviously this keeps going. fix somehow

        first_possibility = False

        if index > 10:
            next_ten = lines[index:index+10]

            hf_or_sf        = ('S.F. No.' in line) or ('H.F. No.' in line)
            was_read        = 'was read' in line
            placed_on       = 'placed' in line

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
                    first_possibility = True

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

    return map(process_vote_chunk, vote_chunks)

# NB: idea for more general rule parser

### Patterns:

### beginning:
### "S.F. No." or "H.F. No." & "committee recommends"
### + (immediately follows a line containing)
### "moved to amend"
### ... (eventually followed by a line containing)
### "The question was taken"
### + (immediately)
### "The roll was called"
### ... (eventually)
### "The motion prevailed" || "The motion did not prevail"

### end:
### "The motion prevailed" || "The motion did not prevail"

def process_amendment_vote_chunk(chunk):
    print '\n'.join(chunk[0:5])
    print '--'
    print
    return chunk

def find_amendment_votes(lines):

    def begin_test(lines, line, index):
        if index > 10:
            hf_or_sf        = ('S.F. No.' in line) or ('H.F. No.' in line)
            recommends      = "committee recommends" in line

            with_the        = "with the following" in line
            subject_to      = "subject to the following" in line

            mark_amendments = with_the or subject_to

            if not all([hf_or_sf, recommends, mark_amendments]):
                return False

            a = "The question was taken"
            b = "The roll was called"
            c = "Those who voted"
            _end = "The motion prevailed"
            _end_b = "The motion did not prevail"
            _a, _b, _c = False, False, False

            for _l in lines[index+2::]:
                if a in _l:
                    _a = True
                if b in _l and _a:
                    _b = True
                if c in _l and _a and _b:
                    _c = True
                if (_end in _l) or (_end_b in _l) and _a and _b and _c:
                    return True
        return False

    def end_test(inner, line, index):
        # Trick here is that sometimes there's other things coming after
        # this that need to be included
        prevail = "The motion prevailed" in line
        nope    = "The motion did not prevail" in line
        following_ammendment = 'moved to amend' in inner[index+1]
        # test preceding S.F. No. / H.F. No. value?
        return (prevail or nope) and not following_ammendment

    vote_chunks = getblocksByTests(lines, begin_test, end_test)
    print len(vote_chunks)

    if len(vote_chunks) == 0:
        return False

    return map(process_amendment_vote_chunk, vote_chunks)


def parse_date(lines):
    """ The date format is pretty consistent, but ISO date formats are
    better, however keep the original date string and day of year.
    """
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

    result = { 'date_iso': formatted
             , 'date_string': date
             , 'session_day': day
             }

    return result

def main(filename, arguments):

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

    votes = find_votes(data)

    if votes:
        logger.info("%s - BILL VOTES: %s" % (filename, str(bool(votes))))
    else:
        logger.warning( "%s - BILL VOTES: ERROR" % filename)

    journal = { 'role_call': names
              , 'bill_votes': votes
              , 'filename': filename
              , 'date': _date_info
              }

    if arguments["--with-amendments"] is True:
        amendment_votes = find_amendment_votes(data)
        journal['amendment_votes'] = amendment_votes
        if amendment_votes:
            logger.info("%s - AMENDMENT VOTES: %s"
                        % (filename, str(bool(amendment_votes)))
                       )
        else:
            logger.warning( "%s - RESOLUTION VOTES: ERROR" % filename)

    # if arguments["--with-resolutions"] is True:
    #     resolution_votes = find_resolution_votes(data)
    #     journal['resolution_votes'] = resolution_votes

    #     if resolution_votes:
    #         logger.info("%s - RESOLUTION VOTES: %s"
    #                     % (filename, str(bool(resolution_votes)))
    #                    )
    #     else:
    #         logger.warning( "%s - RESOLUTION VOTES: ERROR" % filename)

    if arguments["--format"] == "JSON":
        try:
            output = json.dumps(journal, indent=4)
        except:
            logger.error(" *** OMG: Something went way wrong encoding to JSON")
            sys.exit()

    if arguments["<output_file>"] is None:
        output = sys.stdout
    else:
        output = open(arguments["<output_file>"], 'w')

    with output as F:
        print >> F, json.dumps(journal, indent=4)

    return

if __name__ == "__main__":
    arguments = docopt(__doc__, version='0.0.1')

    pdf_file = arguments["<input_file>"]

    try:
        main(pdf_file, arguments)
    except Exception, e:
        import traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, limit=10, file=sys.stdout)
        logger.error(e)
        logger.error(" Error with: %s" % pdf_file)

    sys.exit()


# vim: set ts=4 sw=4 tw=72 syntax=python expandtab:
