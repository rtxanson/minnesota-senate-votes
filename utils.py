#!/usr/bin/env python
""" Some utility functions for processing and chunking lists of lines
by various rules.

These ideally will not need to change much to handle new types of
records, things that deal with actual document structure should be
elsewhere.
"""

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
def getBlocksByTests(lines, begin_test, end_test, include_line_numbers=False):
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

    if include_line_numbers:
        chunks = ([lines[a:b] for a, b in match_indexes], match_indexes)
    else:
        chunks = [lines[a:b] for a, b in match_indexes]
    return chunks

# [str], ( str | regex) -> [[str]]
def chunkby(lines, chunk_str=False, regex=False):
    """ Split a list of strings into chunks, using either
    a regex or a string. """
    import re

    if chunk_str:
        match = lambda x: x.find(chunk_str) > -1
    elif regex:
        _matcher = re.compile(regex).match
        match = lambda x: _matcher(x) is not None

    cur_chunk = []
    for line in lines[1::]:
        if match(line):
            if len(cur_chunk) > 0:
                yield cur_chunk
            cur_chunk = []
            cur_chunk.append(line)
        else:
            cur_chunk.append(line)
