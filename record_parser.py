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
# TODO: things that committees reccommend
#       good example: 20120510119.txt l. ~= 5809
# TODO: adoption of motions


# TODO: output format that includes line numbers that the original data
#       occurred in, anyone actually does spot-checking, this will make it
#       easy to write a quick app to point out where the data came from.

# TODO: keyword mentions
#  - all bill titles mentioned (note several formats, individual and list
#    format, No. vs. Nos.)
#  - committee mentions...?

from docopt import docopt
import sys
import logging
import json
import yaml
import re

from collections import OrderedDict

from utils import *

logger = logging.getLogger("senate")
logger.setLevel("INFO")
logger.addHandler(logging.StreamHandler())
logger.addHandler(logging.FileHandler('last_run_status.txt'))

# TODO: make this a commandline switch later
DEBUG = True

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
    chunk, line_numbers = chunk
    if len(chunk) > 2000:
        logger.error(" * OMG, vote chunk much larger than it should be. ")
        logger.error(" * Parse error in finding vote chunk bounds.")
        logger.error(" * Chunk begins... ")
        logger.error('    > ' + '\n    > '.join(chunk[0:5]))

    bill_title        = False
    affirmative_names = []
    negative_names    = []

    pass_status = [a for a in chunk if 'So the bill' in a][0]

    remove = [ "So the bill, as"
             , "So the bill, "
             , "So the bill "
             ]

    for a in remove:
        pass_status = pass_status.replace(a, '').replace('.', '').strip()

    if "failed" in pass_status:
        _pass = False
    elif "passed" in pass_status:
        _pass = True
    else:
        _pass = "UNKNOWN STATUS"

    if "as amended" in pass_status:
        amended = True
    else:
        amended = False

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

    return  dict([ ('title', bill_title)
                 , ('pass', _pass)
                 , ('status_string', pass_status)
                 , ('amended', amended)
                 , ('yays', len(affirmative_names))
                 , ('nays', len(negative_names))
                 , ('affirmatives', affirmative_names)
                 , ('negatives', negative_names)
                 # TODO: these will need to be adjusted to re-include the 
                 # removed ^L lines.
                 , ('source_document_range', line_numbers)
                 ])

def find_bill_votes(lines):
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
                    if 'passage of the resolution' in _l:
                        first_possibility = False
                        break
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

    vote_chunks = getblocksByTests( lines
                                  , begin_test
                                  , end_test
                                  , include_line_numbers=True
                                  )

    if len(vote_chunks) == 0:
        return False

    return map(process_vote_chunk, zip(*vote_chunks))

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

find_bill_title = re.compile(r'([HS]\.( )?F\. No\. \d+)')
def process_amendment_vote_chunk(chunk):
    chunk, line_numbers = chunk
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

    try:
        pass_status = [a for a in chunk if a.startswith('The motion')][0]
    except:
        print len(chunk)
        print chunk

    failed = "did not prevail"
    passed = "prevailed"

    if failed in pass_status:
        _pass = False
    elif passed in pass_status:
        _pass = True
    else:
        _pass = "UNKNOWN STATUS"

    _vote_aff = 'Those who voted in the affirmative'
    _vote_neg = 'Those who voted in the negative'

    affirmative_names, negative_names = [], []

    negatives_and_affirmatives = getblock(chunk, _vote_aff, _vote_neg)
    if negatives_and_affirmatives:
        affirmatives = negatives_and_affirmatives
        negatives    = getblock(chunk, _vote_neg, 'So the amendment')
    else:
        affirmatives = getblock(chunk, _vote_aff, 'So the amendment')
        negatives    = getblock(chunk, _vote_neg, 'So the amendment')

    if affirmatives:
        # Pop off the inclusive end block match line
        affs = affirmatives[1:len(affirmatives) - 1]
        affirmative_names = parse_vote_name_block(affs)
    if negatives:
        neg = negatives[1:len(negatives) - 1]
        negative_names = parse_vote_name_block(neg)

    log_args = ( str(bill_title)
               , len(affirmative_names)
               , len(negative_names)
               )

    logger.info("    %s (amendment) - yays: %d, nays: %d" % log_args)

    return dict([ ('title', bill_title)
                , ('affirmatives', affirmative_names)
                , ('negatives', negative_names)
                , ('pass', _pass)
                , ('status_string', pass_status)
                , ('yays', len(affirmative_names))
                , ('nays', len(negative_names))
                 # TODO: these will need to be adjusted to re-include the 
                 # removed ^L lines.
                , ('source_document_range', line_numbers)
                ])


def find_amendment_votes(lines):
    # TODO: there may be another way of introducing multiple amendments
    # for a vote, need to look through for S.F. Nos and H.F. Nos

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
                if 'the amendment was stricken' in _l:
                    return False
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
        # this that need to be included, for instance if this line
        # mentions motion status, but the next line mentions another
        # amendment, it's likely to the same bill.
        prevail = "The motion prevailed" in line
        nope    = "The motion did not prevail" in line
        following_amendment = 'moved to amend' in inner[index+1]
        question_taken = 'question was taken' in line
        # Need more accuracy? test preceding S.F. No. / H.F. No. value?
        return (prevail or nope) \
               and not following_amendment \
               and not question_taken

    vote_chunks = getblocksByTests( lines
                                  , begin_test
                                  , end_test
                                  , include_line_numbers=True
                                  )

    if len(vote_chunks) == 0:
        return False

    return map(process_amendment_vote_chunk, zip(*vote_chunks))


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
    day, date = _x[0], _x[1]

    if day:
        day = day.replace(']', '').replace('\n', '').lower()

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

    votes = find_bill_votes(data)

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
        except Exception, e:
            logger.error(" *** OMG: Something went way wrong encoding to JSON")
            print e
            sys.exit()

    if arguments["--format"] == "YAML":
        # TODO: control order and format a bit more
        output = yaml.safe_dump(journal, encoding=None)

    if arguments["<output_file>"] is None:
        target = sys.stdout
    else:
        target = open(arguments["<output_file>"], 'w')

    with target as F:
        print >> F, output

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
