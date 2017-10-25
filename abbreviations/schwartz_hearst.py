import logging
import regex
import sys

"""
A Python 3 refactoring of Vincent Van Asch's Python 2 code at

http://www.cnts.ua.ac.be/~vincent/scripts/abbreviations.py

Based on

A Simple Algorithm for Identifying Abbreviations Definitions in Biomedical Text
A. Schwartz and M. Hearst
Biocomputing, 2003, pp 451-462.

"""

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


class Candidate(str):
    def __new__(cls, start, stop, value):
        obj = str.__new__(cls, value)
        obj.start = start
        obj.stop = stop
        return obj


def yield_lines_from_file(file_path):
    with open(file_path, 'rb') as f:
        for line in f:
            try:
                line = line.decode('utf-8')
            except UnicodeDecodeError:
                line = line.decode('latin-1').encode('utf-8').decode('utf-8')
            line = line.strip()
            yield line


def yield_lines_from_doc(doc_text):
    for line in doc_text.split("\n"):
        yield line.strip()


def best_candidates(sentence):
    """
    :param sentence: line read from input file
    :return: a Candidate iterator
    """

    if '(' in sentence:
        # Check some things first
        if sentence.count('(') != sentence.count(')'):
            raise ValueError("Unbalanced parentheses: {}".format(sentence))

        if sentence.find('(') > sentence.find(')'):
            raise ValueError("First parentheses is right: {}".format(sentence))

        closeindex = -1
        while 1:
            # Look for open parenthesis
            openindex = sentence.find('(', closeindex + 1)

            if openindex == -1: break

            # Look for closing parantheses
            closeindex = openindex + 1
            open = 1
            skip = False
            while open:
                try:
                    char = sentence[closeindex]
                except IndexError:
                    # We found an opening bracket but no associated closing bracket
                    # Skip the opening bracket
                    skip = True
                    break
                if char == '(':
                    open += 1
                elif char == ')':
                    open -= 1
                closeindex += 1

            if skip:
                closeindex = openindex + 1
                continue

            # Output if conditions are met
            start = openindex + 1
            stop = closeindex - 1
            candidate = sentence[start:stop]

            # Take into account whitespace that should be removed
            start = start + len(candidate) - len(candidate.lstrip())
            stop = stop - len(candidate) + len(candidate.rstrip())
            candidate = sentence[start:stop]

            if conditions(candidate):
                yield Candidate(start, stop, candidate)


def conditions(candidate):
    """
    Based on Schwartz&Hearst

    2 <= len(str) <= 10
    len(tokens) <= 2
    re.search('\p{L}', str)
    str[0].isalnum()

    and extra:
    if it matches (\p{L}\.?\s?){2,}
    it is a good candidate.

    :param candidate: candidate abbreviation
    :return: True if this is a good candidate
    """
    if regex.match('(\p{L}\.?\s?){2,}', candidate.lstrip()):
        return True
    if len(candidate) < 2 or len(candidate) > 10:
        return False
    if len(candidate.split()) > 2:
        return False
    if not regex.search('\p{L}', candidate):
        return False
    if not candidate[0].isalnum():
        return False

    return True


def get_definition(candidate, sentence):
    """
    Takes a candidate and a sentence and returns the definition candidate.

    The definintion candidate is the set of tokens (in front of the candidate)
    that starts with a token starting with the first character of the candidate

    :param candidate: candidate abbreviation
    :param sentence: current sentence (single line from input file)
    :return: candidate definition for this abbreviation
    """
    # Take the tokens in front of the candidate
    tokens = sentence[:candidate.start - 2].lower().split()

    # the char that we are looking for
    key = candidate[0].lower()

    # Count the number of tokens that start with the same character as the candidate
    firstchars = [t[0] for t in tokens]

    definition_freq = firstchars.count(key)
    candidate_freq = candidate.lower().count(key)

    # Look for the list of tokens in front of candidate that
    # have a sufficient number of tokens starting with key
    if candidate_freq <= definition_freq:
        # we should at least have a good number of starts
        count = 0
        start = 0
        startindex = len(firstchars) - 1
        while count < candidate_freq:
            if abs(start) > len(firstchars):
                raise ValueError("candiate {} not found".format(candidate))
            start -= 1
            # Look up key in the definition
            try:
                startindex = firstchars.index(key, len(firstchars) + start)
            except ValueError:
                pass

            # Count the number of keys in definition
            count = firstchars[startindex:].count(key)

        # We found enough keys in the definition so return the definition as a definition candidate
        start = len(' '.join(tokens[:startindex]))
        stop = candidate.start - 1
        candidate = sentence[start:stop]

        # Remove whitespace
        start = start + len(candidate) - len(candidate.lstrip())
        stop = stop - len(candidate) + len(candidate.rstrip())
        candidate = sentence[start:stop]

        return Candidate(start, stop, candidate)

    else:
        raise ValueError('There are less keys in the tokens in front of candidate than there are in the candidate')


def select_definition(definition, abbrev):
    """
    Takes a definition candidate and an abbreviation candidate
    and returns True if the chars in the abbreviation occur in the definition

    Based on
    A simple algorithm for identifying abbreviation definitions in biomedical texts, Schwartz & Hearst
    :param definition: candidate definition
    :param abbrev: candidate abbreviation
    :return:
    """

    if len(definition) < len(abbrev):
        raise ValueError('Abbreviation is longer than definition')

    if abbrev in definition.split():
        raise ValueError('Abbreviation is full word of definition')

    sindex = -1
    lindex = -1

    while 1:
        try:
            longchar = definition[lindex].lower()
        except IndexError:
            raise

        shortchar = abbrev[sindex].lower()

        if not shortchar.isalnum():
            sindex -= 1

        if sindex == -1 * len(abbrev):
            if shortchar == longchar:
                if lindex == -1 * len(definition) or not definition[lindex - 1].isalnum():
                    break
                else:
                    lindex -= 1
            else:
                lindex -= 1
                if lindex == -1 * (len(definition) + 1):
                    raise ValueError("definition {} was not found in {}".format(abbrev, definition))

        else:
            if shortchar == longchar:
                sindex -= 1
                lindex -= 1
            else:
                lindex -= 1

    definition = Candidate(definition.start, definition.stop, definition[lindex:len(definition)])

    tokens = len(definition.split())
    length = len(abbrev)

    if tokens > min([length + 5, length * 2]):
        raise ValueError("did not meet min(|A|+5, |A|*2) constraint")

    # Do not return definitions that contain unbalanced parentheses
    if definition.count('(') != definition.count(')'):
        raise ValueError("Unbalanced parentheses not allowed in a definition")

    return definition


def extract_abbreviation_definition_pairs(file_path=None, doc_text=None):
    abbrev_map = dict()
    omit = 0
    written = 0
    if file_path:
        sentence_iterator = enumerate(yield_lines_from_file(file_path))
    elif doc_text:
        sentence_iterator = enumerate(yield_lines_from_doc(doc_text))
    else:
        return abbrev_map

    for i, sentence in sentence_iterator:
        try:
            for candidate in best_candidates(sentence):
                try:
                    definition = get_definition(candidate, sentence)
                except ValueError as e:
                    log.debug("{} Omitting candidate {}. Reason: {}".format(i, candidate, e.args[0]))
                    omit += 1
                else:
                    try:
                        definition = select_definition(definition, candidate)
                    except IndexError:
                        log.debug("{} Omitting definition {} for candidate {}".format(i, definition, candidate))
                        omit += 1
                    except ValueError as e:
                        log.debug("{} Omitting definition {} for candidate {}. Reason: {}".format(i, definition, candidate, e.args[0]))
                        omit += 1
                    else:
                        abbrev_map[candidate] = definition
                        written += 1
        except ValueError as e:
            log.debug("Error: {}".format(e.args[0]))
    log.debug("{} abbreviations detected and kept ({} omitted)".format(written, omit))
    return abbrev_map


if __name__ == '__main__':
    print(extract_abbreviation_definition_pairs(file_path=sys.argv[1]))