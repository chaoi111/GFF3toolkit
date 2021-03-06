#! /usr/local/bin/python2.7
# -*- coding: utf-8 -*-
# Contributed by Mei-Ju May Chen <arbula [at] gmail [dot] com> (2016)

"""
QC functions for processing multiple features within a model (intra-model) in GFF3 file.
"""
from __future__ import print_function

#from collections import OrderedDict # not available in 2.6
from collections import defaultdict
from itertools import groupby
try:
    from urllib import quote, unquote
except ImportError:
    from urllib.parse import quote, unquote
from textwrap import wrap
import sys
import re
import logging
logger = logging.getLogger(__name__)
#log.basicConfig(level=logging.DEBUG, format='%(levelname)-8s %(message)s')
logger.setLevel(logging.INFO)
if not logger.handlers:
    lh = logging.StreamHandler()
    lh.setFormatter(logging.Formatter('%(levelname)-8s %(message)s'))
    logger.addHandler(lh)
from os.path import dirname
if dirname(__file__) == '':
    lib_path = '../../lib'
else:
    lib_path = dirname(__file__) + '/../../lib'
sys.path.insert(1, lib_path)
from gff3_modified import Gff3
import function4gff
import ERROR
if dirname(__file__) == '':
    bin_path = '../../bin'
else:
    bin_path = dirname(__file__) + '/../../bin'
sys.path.insert(1, bin_path)
import gff3_to_fasta

__version__ = '0.0.1'

ERROR_INFO = ERROR.INFO 

def check_redundant_length(gff, rootline):
    eCode = 'Ema0001'
    result = dict()

    flag = 0
    gene_start = rootline['start']
    gene_end = rootline['end']
    gene_len = gene_end - gene_start + 1

    children = rootline['children']
    c_start = list()
    c_end = list()
    for child in children:
        c_start.append(child['start'])
        c_end.append(child['end'])
    if len(c_start) > 0 and len(c_end) > 0:
        min_start = min(c_start)
        max_end = max(c_end)
        child_len = max_end - min_start + 1
        #print(min_start, c_start, max_end, c_end)


        if ((min_start != gene_start or max_end != gene_end) and (gene_len > child_len)):
            result['eLines']=list()
            result['ID'] = [rootline['attributes']['ID']]
            result['line_num'] = ['Line {0:s}'.format(str(rootline['line_index'] + 1))]
            result['eCode'] = eCode
            for child in children:
                result['eLines'].append(child)
            result['eTag'] = ERROR_INFO[eCode]
            flag += 1

    if flag > 0:
        gff.add_line_error(rootline, {'message': ERROR_INFO[eCode], 'error_type': 'FEATURE_TYPE', 'eCode': eCode})
    if len(result):
        return [result]

def check_internal_stop(gff, rootline):
    eCode = 'Ema0002'
    result = list()
   
    children = rootline['children']
    for child in children:
        r = dict()
        flag = 0
        segments = []
        gchildren = child['children']
        for gchild in gchildren:
            if gchild['type'] == 'CDS':
                segments.append(gchild)

        sort_seg = function4gff.featureSort(segments)
        if gchild['strand'] == '-':
            sort_seg = function4gff.featureSort(segments, reverse=True)

        tmpseq = ''
        tmpindex = list()
        count = 0
        for s in sort_seg:
            if count == 0:
                start, end = int, int
                line = s
                if line['type'] == 'CDS':
                    if not type(line['phase']) == int:
                        sys.exit('[Error] No phase informatin!\n\t\t- Line {0:s}: {1:s}'.format(str(line['line_index']+1), line['line_raw']))
                    start = line['start']+line['phase']
                    end = line['end']
                    if line['strand'] == '-':
                        start = line['start']
                        end = line['end']-line['phase']
                else:
                    start = line['start']
                    end = line['end']
             
                s['start'] = start
                s['end'] = end
                s['phase'] = 0
            tmpseq = tmpseq + gff3_to_fasta.get_subseq(gff, s)
            index = list(range(s['start']+s['phase'], s['end']+1, 3))
            if line['strand'] == '-':
                index = list(range(s['end']-s['phase'], s['start']-1, -3))
            tmpindex.extend(index)
            #print(s['start'], s['end'], s['phase'])
            count += 1
        aa = gff3_to_fasta.translator(tmpseq)
        stop = [m.start() for m in re.finditer('\*', aa)]
        bp = list()
        for i in stop:
            if i < len(aa)-1:
                bp.append(str(tmpindex[i]))


        if len(bp):
#            print(tmpindex, len(tmpindex), tmpseq, len(tmpseq), aa, len(aa), stop, bp)
 #           print(' ,and '.join(bp))
            r['ID'] = [child['attributes']['ID']]
            r['line_num'] = ['Line {0:s}'.format(str(child['line_index'] + 1))]
            r['eCode'] = eCode
            r['eLines']=list()
            r['eLines'].append(child)
            r['eTag'] = '{0:s} at bp {1:s}'.format(ERROR_INFO[eCode], ', and '.join(bp))
            flag += 1

        if flag > 0:
            result.append(r)
            gff.add_line_error(rootline, {'message': ERROR_INFO[eCode], 'error_type': 'FEATURE_TYPE', 'eCode': eCode})

    if len(result):
        return result
 

def check_incomplete(gff, rootline):
    eCode = 'Ema0004'
    result = dict()

    flag = 0
    if rootline['type'] == 'gene':
        children = rootline['children']
        mRNA = 0
        eflag = 0
        for child in children:
            if child['type'] == 'mRNA':
                mRNA += 1
                gchildren = child['children']
                exon = 0
                cds = 0
                for gchild in gchildren:
                    if gchild['type'] == 'exon':
                        exon += 1
                    elif gchild['type'] == 'CDS':
                        cds += 1
                if exon==0 or cds ==0:
                    eflag += 1
                    
        if mRNA == 0:
            eflag += 1

        if eflag > 0:
            result['ID'] = [rootline['attributes']['ID']]
            result['line_num'] = ['Line {0:s}'.format(str(rootline['line_index'] + 1))]
            result['eCode'] = eCode
            result['eLines']=list()
            result['eLines'].append(rootline)
            result['eTag'] = ERROR_INFO[eCode]
            flag += 1

    if flag > 0:
        gff.add_line_error(rootline, {'message': ERROR_INFO[eCode], 'error_type': 'FEATURE_TYPE', 'eCode': eCode})

    if len(result):
        return [result]
       
                


def check_pseudo_child_type(gff, rootline):
    eCode = 'Ema0005'
    result = dict()

    if rootline['type'] == 'pseudogene':
        children = rootline['children']
        flag = 0
        for child in children:
            if child['type'] == 'transcript' or child['type'] == 'pseudogenic_transcript':
                pass
            else:
                flag += 1
                if len(result):
                    result['eLines'].append(child)
                else:
                    result['ID'] = [rootline['attributes']['ID']]
                    result['line_num'] = ['Line {0:s}'.format(str(rootline['line_index'] + 1))]
                    result['eCode'] = eCode
                    result['eLines'] = [child]
                    result['eTag'] = ERROR_INFO[eCode]
        if flag > 0:
            gff.add_line_error(rootline, {'message': ERROR_INFO[eCode], 'error_type': 'FEATURE_TYPE', 'eCode': eCode})
    if len(result):
        return [result]

def main(gff, logger=None):
    function4gff.FIX_MISSING_ATTR(gff, logger=logger)


    roots = [line for line in gff.lines if line['line_type']=='feature' and not line['attributes'].has_key('Parent')]
    error_set=list()
    for root in roots:
        r = check_pseudo_child_type(gff, root)
        if not r == None:
            error_set.extend(r)
        r = None
        r = check_redundant_length(gff, root)
        if not r == None:
            error_set.extend(r)
        r = None
        r = check_incomplete(gff, root)
        if not r == None:
            error_set.extend(r)
        r = None
        r = check_internal_stop(gff, root)
        if not r == None:
            error_set.extend(r)
        r = None


#    for e in error_set:
#        print('{0:s}\t{1:s}\t{2:s}\n'.format(e['ID'], e['eCode'], e['eTag']))

    if len(error_set): 
        return(error_set)


if __name__ == '__main__':
    logger_stderr = logging.getLogger(__name__+'stderr')
    logger_stderr.setLevel(logging.INFO)
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(logging.Formatter('%(levelname)-8s %(message)s'))
    logger_stderr.addHandler(stderr_handler)
    logger_null = logging.getLogger(__name__+'null')
    null_handler = logging.NullHandler()
    logger_null.addHandler(null_handler)
    import argparse
    from textwrap import dedent
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=dedent("""\
    QC functions for processing multiple features within a model (intra-model) in GFF3 file.
    
    Testing enviroment:
    1. Python 2.7

    Inputs:
    1. GFF3: reads from STDIN by default, may specify the file name with the -g argument

    Outputs:
    1. GFF3: fixed GFF file

    """))
    parser.add_argument('-g', '--gff', type=str, help='Summary Report from Monica (default: STDIN)') 
    parser.add_argument('-f', '--fasta', type=str, help='Genome sequences in FASTA format')
    parser.add_argument('-o', '--output', type=str, help='Output file name (default: STDIN)')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    
    args = parser.parse_args()

    if args.gff:
        logger_stderr.info('Checking gff file (%s)...', args.gff)
    elif not sys.stdin.isatty(): # if STDIN connected to pipe or file
        args.gff = sys.stdin
        logger_stderr.info('Reading from STDIN...')
    else: # no input
        parser.print_help()
        sys.exit(1)

    if args.fasta:
        logger_stderr.info('Checking genome fasta (%s)...', args.fasta)
    elif not sys.stdin.isatty(): # if STDIN connected to pipe or file
        args.fasta = sys.stdin
        logger_stderr.info('Reading from STDIN...')
    else: # no input
        parser.print_help()
        logger_stderr.error('Required field -f missing...')
        sys.exit(1)

    if args.output:
        logger_stderr.info('Specifying output file name: (%s)...\n', args.output)
        report_fh = open(args.output, 'wb')
    else:
        report_fh = open('intra_model_report.txt', 'wb')
   
    gff3 = Gff3(gff_file=args.gff, fasta_external=args.fasta, logger=logger_null)
    main(gff3, logger=logger_stderr)
