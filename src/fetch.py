#!/usr/bin/python
#-*-coding: utf8

#
#   Author:  Cliff Chao-kuan Lu <clifflu@gmail.com>
#   License: MIT License
#

#
# todo: currency other than USD
#

import os
import json
import sys
import re
import exceptions

#
# Util
#

def aws_url(fn):
    return CONFIG['filelist']['prefix'] + fn + CONFIG['filelist']['appendix']

def local_fn(fn):
    return os.path.join(PATH['TMP'], fn + CONFIG['filelist']['appendix'])

def build_lookup_table(src, dest):
    for key in src:
        for alias in src[key]:
            dest[alias] = key

def num(str):
    import ast
    try:
        return ast.literal_eval(str)
    except exceptions.StandardError:
        return None

def guess_os(fn):
    for os in CONFIG['tags']['oses']:
        if re.search('^%s-' % os , fn, re.I):
            return os
    return False

def guess_term(fn):
    """猜測可能的 term; 由於 RI 合約年數不由檔名決定，因此只回傳 od|l|m|h 或 False"""
    t = re.search('-(od|ri-(?:heavy|medium|light))$', fn)
    if t:
        if t.group(1) == 'od':
            return 'od'
        elif t.group(1) == 'ri-heavy':
            return 'h'
        elif t.group(1) == 'ri-medium':
            return 'm'
        elif t.group(1) == 'ri-light':
            return 'l'
    return False

def is_term_od(term):
    return term == 'od'

#
# Parse JSON from AWS
#

def parse_file(fn, tbl):
    """開啟並分析 fn，並將資料存至 tbl.
    由檔名猜測對應的 os 與 term."""
    
    c_os = guess_os(fn)
    c_term = guess_term(fn)

    if not (c_os and c_term):
        return
    
    with open(local_fn(fn), 'r') as fp:
        src = json.load(fp)

        # todo: Currency and Version check

        for src_regional in src['config']['regions']:
            c_region = src_regional['region']

            if c_region in CONFIG['remap']['regions']:
                c_region = CONFIG['remap']['regions'][c_region]
            
            # todo: region check

            if not c_region in tbl.keys():
                tbl[c_region] = {}

            if not c_os in tbl[c_region].keys():
                tbl[c_region][c_os] = {}

            parse_instance_type(src_regional['instanceTypes'], c_term, tbl[c_region][c_os])

def parse_instance_type(src_its, c_term, tbl_its ):
    for src_it in src_its:
        c_type = src_it['type']

        if c_type in CONFIG['remap']['instances']:
            c_type = CONFIG['remap']['instances'][c_type]

        if c_type not in tbl_its.keys():
            tbl_its[c_type] = {}

        for src_sz in src_it['sizes']:
            c_size = src_sz['size']

            if c_size not in tbl_its[c_type].keys():
                tbl_its[c_type][c_size] = {}

            if is_term_od(c_term):
                parse_od(src_sz, tbl_its[c_type][c_size])
            else:
                parse_ri(src_sz, c_term, tbl_its[c_type][c_size])

def parse_od(src_sz, tbl_sz):
    src_prices = src_sz['valueColumns'][0]['prices']
    tbl_sz['od'] = [num(src_prices['USD'])]

def parse_ri(src_sz, c_term, tbl_sz):
    src_vcs = src_sz['valueColumns']

    for vc in src_vcs :
        if vc['name'] == 'yrTerm1':
            upfront_1 = num(vc['prices']['USD'])
        elif vc['name'] == 'yrTerm3':
            upfront_3 = num(vc['prices']['USD'])
        elif vc['name'] == 'yrTerm1Hourly':
            hourly_1 = num(vc['prices']['USD'])
        elif vc['name'] == 'yrTerm3Hourly':
            hourly_3 = num(vc['prices']['USD'])

    if upfront_1 and hourly_1:
        tbl_sz['y1%s' % c_term] = [hourly_1, upfront_1]

    if upfront_3 and hourly_3:
        tbl_sz['y3%s' % c_term] = [hourly_3, upfront_3]


#
# Remove None (null) and N/A
#
def strip_nulls(obj):
    """除去 obj 及其子成員中，只包含 None 的 list, 以及不包含任何成員的 list 或 dict"""
    while strip_null_worker(obj) > 0:
        pass

    return obj

def strip_null_worker(obj):
    fired = 0
    tbd = []

    if type(obj) is list:
        for i in range(len(obj)-1):
            sub = obj[i]

            if (type(sub) is list and all(map(lambda x: x is None, sub))):
                tbd.append(i)
                fired = 1

            if (type(sub) is list or type(sub) is dict):
                if len(sub) == 0:
                    tbd.append(i)
                    fired = 1
                else:
                    fired = strip_null_worker(sub) or fired

        for i in sorted(tbd, reverse=True):
            del(obj[i])

    elif type(obj) is dict:
        for i in obj:
            sub = obj[i]

            if (type(sub) is list and all(map(lambda x: x is None, sub))):
                tbd.append(i)
                fired = 1

            if (type(sub) is list or type(sub) is dict):
                if len(sub) == 0:
                    tbd.append(i)
                    fired = 1
                else:
                    fired = strip_null_worker(sub) or fired
        for i in tbd:
            del(obj[i])

    return fired

#
# Procedural
#

def proc_args():
    try:
        for arg in sys.argv:
            idx = sys.argv.index(arg)

            if (arg in ('-c', '--cleanup')):
                CONFIG['cmdline']['cleanup'] = True
                continue
            elif (arg in ('-d', '--days')):
                CONFIG['cmdline']['refetch_days'] = num(sys.argv[idx+1])
                continue
            elif (arg in ('-f', '--force-fetch')):
                CONFIG['cmdline']['force_fetch'] = True
                continue
            elif (arg in ('-h', '--help')):
                usage()
                continue
            elif (arg in ('-i', '--indent')):
                CONFIG['cmdline']['output_indent'] = num(sys.argv[idx+1])
                CONFIG['cmdline']['pretty_output'] = True
                continue
            elif (arg in ('-o', '--output-file')):
                CONFIG['cmdline']['output_fn'] = sys.argv[idx+1]
                continue
            elif (arg in ('-p', '--pretty-output')):
                CONFIG['cmdline']['pretty_output'] = True
                continue
            elif (arg in ('-t', '--tmp-dir')):
                PATH['TMP'] = sys.argv[idx+1]
                continue

            # not found, probably param to other directives
            if idx > 1 and sys.argv[idx-1] in ('-d', '--days', '-i', '--indent', '-o', '--output-file', '-t', '--tmp-dir'):
                continue

            # script itself
            if idx == 0: 
                continue

            usage()

    except exceptions.StandardError:
        usage()

def need_fetch():
    import time, datetime

    past = datetime.datetime.now() - datetime.timedelta(days=CONFIG['cmdline']['refetch_days'])
    past = time.mktime(past.timetuple())

    if CONFIG['cmdline']['force_fetch']:
        return True
    
    for fn in CONFIG['filelist']['files']:
        fn = local_fn(fn)
        
        if not os.path.isfile(fn):
            return True

        if (os.path.getmtime(fn) < past):
            return True

    return False

def fetch():
    """Fetch data files from AWS"""
    import urllib

    for fn in CONFIG['filelist']['files']:
        urllib.urlretrieve(aws_url(fn), local_fn(fn))

def convert():
    """Convert downloaded files"""
    output = {}
    fetch_list = CONFIG['filelist']['files']
    for fn in fetch_list:
        parse_file(fn, output)

    return strip_nulls(output)

def output(str):
    if CONFIG['cmdline']['pretty_output']:
        str = json.dumps(str, indent=CONFIG['cmdline']['output_indent'])
    else:
        str = json.dumps(str)

    if CONFIG['cmdline']['output_fn']:
        with open(CONFIG['cmdline']['output_fn'], "w") as fp:
            fp.write(str + "\n")
    else:
        print(str)

def cleanup():
    if CONFIG['cmdline']['cleanup']:
        for fn in CONFIG['filelist']['files']:
            fn = local_fn(fn)
            if os.path.isfile(fn):
                os.unlink(fn)

def usage():
    print("usage: %s [options]" % sys.argv[0])
    print("Options and arguments:")
    print("-c\t\t: cleanup tmp files after completion")
    print("-d days\t\t: days before automatic refetch, default=7")
    print("-f \t\t: force fetch, ignore file age check")
    print("-h\t\t: print this help message")
    print("-i width\t: set indentation, implies pretty output (-p)")
    print("-o file\t\t: output to file, not than stdout")
    print("-p \t\t: pretty output, file gets larger")
    print("-t dir\t\t: override tmp path")
    sys.exit(0)



#
# Project Paths
#

PATH = {}

PATH['ROOT']    = os.path.realpath(__file__ + '/../..')
PATH['CONFIG']  = os.path.join(PATH['ROOT'], 'config')
PATH['TMP']     = os.path.join(PATH['ROOT'], 'tmp')

#
# Load Config Files
#

CONFIG = {'cmdline': None, 'filelist': None, 'remap': None, 'tags': None}

for fn in CONFIG:
    with open(os.path.join(PATH['CONFIG'], fn + '.json'), 'r') as fp:
        CONFIG[fn] = json.load(fp)

#
# Build Lookup Tables
#

for tbl_name in CONFIG['remap']['_lookup']:
    CONFIG['remap'][tbl_name] = {}
    build_lookup_table(CONFIG['remap']['_lookup'][tbl_name], CONFIG['remap'][tbl_name])

#
# Main
#

if __name__ == '__main__':
    proc_args();
    if need_fetch(): fetch()
    output(convert())
    cleanup()