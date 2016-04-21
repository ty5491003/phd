#!/usr/bin/env python3
#
# Preprocess the raw dataset.
#
# TODO:
#
#   Use a fixed file preprocessing pipeline, not a bunch of different
#   map operations.
#
# Extrapolated data:
#
# Try compiling each source to LLVM bytecode
# For those that build, run static analysis to generate feature vectors
#
import os
import re
import shutil
import sqlite3
import sys

from subprocess import Popen,PIPE,STDOUT
from multiprocessing import Pool


def usage():
    print('Usage: {} <db>'.format(sys.argv[0]))


# Write OpenCL files.
#
def ocl_writer_worker(db_path):
    print('ocl writer worker ...')

    out_dir = 'cl'
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    db = sqlite3.connect(db_path)
    c = db.cursor()

    c.execute('SELECT sha,path,contents FROM ContentFiles GROUP BY sha')
    query = c.fetchall()

    files_added_counter = 0
    files_skipped_counter = 0
    files_error_counter = 0
    for row in query:
        sha, path, contents = row
        _, extension = os.path.splitext(path)
        try:
            out_path = out_dir + '/' + sha + extension
            if os.path.exists(out_path):
                files_skipped_counter += 1
            else:
                with open(out_path, 'w') as out:
                    out.write(contents)
                files_added_counter += 1
        except Exception as e:
            out_path = out_dir + '/' + sha + '.error'
            with open(out_path, 'w') as out:
                out.write(str(e) + '\n')
            files_error_counter += 1
    return (
        'ocl files stats: {} added, {} skipped, {} errors.'
        .format(files_added_counter, files_skipped_counter,
                files_error_counter))


def preprocess_cl(src):
    clang = os.path.expanduser('~/phd/tools/llvm/build/bin/clang')
    libclc = os.path.expanduser('~/phd/extern/libclc')

    cmd = [
        clang, '-Dcl_clang_storage_class_specifiers',
        '-I', '{}/generic/include'.format(libclc),
        '-include', '{}/generic/include/clc/clc.h'.format(libclc),
        '-target', 'nvptx64-nvidia-nvcl',
        '-DM_PI=3.14'
        '-x', 'cl', '-E',
        '-c', '-', '-o', '-'
    ]

    process = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate(src)

    if process.returncode != 0:
        raise Exception(stderr.decode('utf-8'))
    return stdout


def rewrite_cl(in_path, out_path):
    ld_path = os.path.expanduser('~/phd/tools/llvm/build/lib/')
    libclc = os.path.expanduser('~/phd/extern/libclc')
    rewriter = os.path.expanduser('~/phd/lab/ml/rewriter')

    extra_args = [
        '-Dcl_clang_storage_class_specifiers',
        '-I{}/generic/include'.format(libclc),
        '-include', '{}/generic/include/clc/clc.h'.format(libclc),
        '-target', 'nvptx64-nvidia-nvcl',
        '-DM_PI=3.14',
        '-xcl'
    ]

    cmd = ([rewriter, in_path ]
           + ['-extra-arg=' + x for x in extra_args] + ['--'])

    process = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                    env = {'LD_LIBRARY_PATH': ld_path})
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise Exception(stderr.decode('utf-8'))

    formatted = clangformat_ocl(stdout)

    with open(out_path, 'wb') as out:
        out.write(formatted)


def rewrite_cl_worker(*args, **kwargs):
    print('rewrite cl worker ...')

    in_dir = 'cl-tidy'
    out_dir = 'cl-rewrite'
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    files_added_counter = 0
    files_skipped_counter = 0
    errors_counter = 0

    for f in os.listdir(in_dir):
        in_path = in_dir + '/' + f
        out_path = out_dir + '/' + f

        if os.path.exists(out_path):
            files_skipped_counter += 1
        else:
            try:
                rewrite_cl(in_path, out_path)
                files_added_counter += 1
            except Exception as e:
                errors_counter += 1

    return ('rewrite cl stats: {} added, {} skipped, {} errors.'
            .format(files_added_counter, files_skipped_counter, errors_counter))


def compile_cl_bytecode(src):
    clang = os.path.expanduser('~/phd/tools/llvm/build/bin/clang')
    libclc = os.path.expanduser('~/phd/extern/libclc')

    cmd = [
        clang, '-Dcl_clang_storage_class_specifiers',
        '-I', '{}/generic/include'.format(libclc),
        '-include', '{}/generic/include/clc/clc.h'.format(libclc),
        '-target', 'nvptx64-nvidia-nvcl',
        '-x', 'cl', '-emit-llvm', '-S',
        '-c', '-', '-o', '-'
    ]

    process = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate(src)

    if process.returncode != 0:
        raise Exception(stderr.decode('utf-8'))
    return stdout


# Compile OpenCL files into bytecode.
#
def ocl_builder_worker(db_path):
    print('ocl builder worker ...')

    out_dir = 'bc'
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    db = sqlite3.connect(db_path)
    c = db.cursor()

    c.execute('SELECT sha,path,contents FROM ContentFiles GROUP BY sha')
    query = c.fetchall()

    counter = 0
    files_added_counter = 0
    files_skipped_counter = 0
    files_error_counter = 0
    for row in query:
        counter += 1
        sha, path, contents = row
        print('\r\033[K', counter, path, end='')
        sys.stdout.flush()

        out_path = out_dir + '/' + sha + '.bc'
        err_path = out_dir + '/' + sha + '.error'

        # Check to see if we've already compiled it.
        if (os.path.exists(out_path) or
            os.path.exists(err_path)):
            files_skipped_counter += 1
        else:
            try:
                bc = compile_cl_bytecode(contents.encode('utf-8'))

                # Add to database.
                c = db.cursor()
                c.execute('INSERT INTO Bytecodes VALUES(?,?)',
                          (sha,bc))

                # Write file.
                with open(out_path, 'wb') as out:
                    out.write(bc)
                files_added_counter += 1
            except Exception as e:
                # Add to database.
                c = db.cursor()
                c.execute('INSERT INTO BytecodeErrors VALUES(?,?)',
                          (sha, str(e)))

                out_path = out_dir + '/' + sha + '.error'
                with open(out_path, 'w') as out:
                    out.write(str(e) + '\n')
                files_error_counter += 1

            db.commit()

    # Clear output
    print('\r\033[K', end='')
    sys.stdout.flush()
    return (
        'ocl bytecode stats: {} added, {} skipped, {} errors.'
        .format(files_added_counter, files_skipped_counter,
                files_error_counter))


# Preprocess OpenCL files.
#
def ocl_preprocessor_worker(db_path):
    print('ocl preprocessor worker ...')

    db = sqlite3.connect(db_path)
    c = db.cursor()

    c.execute('SELECT sha,path,contents FROM ContentFiles GROUP BY sha')
    query = c.fetchall()

    files_added_counter = 0
    files_skipped_counter = 0
    files_error_counter = 0
    for row in query:
        sha, path, contents = row

        # Check to see if we've already compiled it.
        c = db.cursor()
        c.execute('SELECT sha FROM Preprocessed WHERE sha=?', (sha,))
        is_preprocessed = c.fetchone()
        c.execute('SELECT sha FROM PreprocessedErrors WHERE sha=?', (sha,))
        is_preprocessed_error = c.fetchone()

        if (is_preprocessed or is_preprocessed_error):
            files_skipped_counter += 1
        else:
            try:
                cl = preprocess_cl(contents.encode('utf-8'))

                # Add to database.
                c.execute('INSERT INTO Preprocessed VALUES(?,?)',
                          (sha,cl))
                files_added_counter += 1
            except Exception as e:
                # Add to database.
                c = db.cursor()
                c.execute('INSERT INTO PreprocessedErrors VALUES(?,?)',
                          (sha, str(e)))
                files_error_counter += 1
            db.commit()

    return (
        'ocl preprocessor stats: {} added, {} skipped, {} errors.'
        .format(files_added_counter, files_skipped_counter,
                files_error_counter))


_instcount_re = re.compile("^(?P<count>\d+) instcount - Number of (?P<type>.+)")


def parse_instcounts(txt):
    lines = [x.strip() for x in txt.split("\n")]
    counts = {}

    # Build a list of counts for each type.
    for line in lines:
        match = re.search(_instcount_re, line)
        if match:
            count = int(match.group("count"))
            key = match.group("type")
            if key in counts:
                counts[key].append(count)
            else:
                counts[key] = [count]

    # Sum all counts.
    for key in counts:
        counts[key] = sum(counts[key])

    return counts


_sql_rm_chars = re.compile('[\(\)]')
_sql_sub_chars = re.compile('-')


def escape_sql_key(key):
    return re.sub(_sql_sub_chars, '_',
                  re.sub(_sql_rm_chars, '', '_'.join(key.split(' '))))


def instcounts2ratios(counts):
    if not len(counts):
        return {}

    ratios = {}
    total_key = "instructions (of all types)"
    non_ratio_keys = [
        total_key
    ]
    total = float(counts[total_key])

    for key in non_ratio_keys:
        ratios[escape_sql_key(key)] = counts[key]

    for key in counts:
        if key not in non_ratio_keys:
            # Copy count
            ratios[escape_sql_key(key)] = counts[key]
            # Insert ratio
            ratios[escape_sql_key('ratio_' + key)] = float(counts[key]) / total

    return ratios


def sql_insert_dict(c, table, data):
    cmd = ("INSERT INTO {table}({cols}) VALUES({vals})"
           .format(table=table,
                   cols=','.join(data.keys()),
                   vals=','.join(['?'] * len(data))))

    vals = tuple(data.values())
    c.execute(cmd, tuple(data.values()))


def bytecode_features(bc):
    opt = os.path.expanduser('~/phd/tools/llvm/build/bin/opt')

    cmd = [
        opt, '-analyze', '-stats', '-instcount', '-'
    ]

    # LLVM pass output pritns to stderr, so we'll pipe stderr to
    # stdout.
    process = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout, _ = process.communicate(bc)

    if process.returncode != 0:
        raise Exception(stdout.decode('utf-8'))

    instcounts = parse_instcounts(stdout.decode('utf-8'))
    instratios = instcounts2ratios(instcounts)

    return instratios

def clangformat_ocl(src):
    clangformat = os.path.expanduser('~/phd/tools/llvm/build/bin/clang-format')
    cmd = [
        clangformat, '-style=google'
    ]

    process = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate(src)

    if process.returncode != 0:
        raise Exception(stderr.decode('utf-8'))

    return stdout


def print_bytecode_features(db_path):
    db = sqlite3.connect(db_path)
    c = db.cursor()

    c.execute('SELECT sha,contents FROM Bytecodes')
    query = c.fetchall()

    uniq_features = set()
    for row in query:
        sha, contents = row

        features = bytecode_features(contents)
        # Add the table key
        features['sha'] = sha
        for key in features.keys():
            uniq_features.add(key)

    print('Features:')
    for feature in uniq_features:
        print('        ', feature)


def bytecode_features_worker(db_path):
    print('bc features worker ...')

    db = sqlite3.connect(db_path)
    c = db.cursor()

    c.execute('SELECT sha,contents FROM Bytecodes')
    query = c.fetchall()

    features_added_counter = 0
    features_skipped_counter = 0

    for row in query:
        sha, contents = row

        # Check to see if we've already compiled it.
        c = db.cursor()
        c.execute('SELECT sha FROM BytecodeFeatures WHERE sha=?', (sha,))
        is_cached = c.fetchone()

        if is_cached:
            features_skipped_counter += 1
        else:
            features = bytecode_features(contents)
            # Add the table key
            features['sha'] = sha
            sql_insert_dict(c, 'BytecodeFeatures', features)
            db.commit()
            features_added_counter += 1

    return (
        'bc features stats: {} added, {} skipped.'
        .format(features_added_counter, features_skipped_counter))


def ocl_tidy_worker(db_path):
    print('ocl tidy worker ...')

    out_dir = 'cl-tidy'
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    db = sqlite3.connect(db_path)
    c = db.cursor()

    c.execute('SELECT Preprocessed.sha,Preprocessed.contents '
              'FROM BytecodeFeatures '
              'LEFT JOIN Preprocessed ON BytecodeFeatures.sha=Preprocessed.sha '
              'WHERE instructions_of_all_types > 0')
    query = c.fetchall()

    files_added_counter = 0
    files_skipped_counter = 0

    debug = 0
    for row in query:
        sha, contents = row

        out_path = out_dir + '/' + sha + '.cl'

        # Check to see if we've already tidied it.
        c = db.cursor()
        c.execute('SELECT sha FROM OpenCLTidy WHERE sha=?', (sha,))
        is_cached = c.fetchone()
        is_file = os.path.exists(out_path)

        if is_cached and is_file:
            files_skipped_counter += 1
        else:
            src = contents.decode('utf-8')
            lines = src.split('\n')

            # Strip all the includes:
            for i,line in enumerate(lines):
                if line == '# 1 "<stdin>" 2':
                    break
            src = '\n'.join(lines[i+1:]).strip()

            # Strip lines beginning with '#' (that's preprocessor
            # stuff):
            src = '\n'.join([line for line in src.split('\n')
                             if not line.startswith('#')])

            # Run clang-format on the source:
            src = clangformat_ocl(src.encode('utf-8')).decode('utf-8')

            # Add the trailing newline:
            src += '\n'

            # Write to file:
            if not is_file:
                with open(out_path, 'w') as out:
                    out.write(src)

            # Insert into database:
            if not is_cached:
                c.execute('INSERT INTO OpenCLTidy VALUES(?,?)',
                          (sha,src))
                db.commit()
            files_added_counter += 1

    return ('ocl tidy stats: {} added, {} skipped.'
            .format(files_added_counter, files_skipped_counter))


def main():
    if len(sys.argv) != 2:
        usage()
        sys.exit(1)

    db_path = sys.argv[1]

    pool = Pool(processes=4)

    # Worker process pool
    jobs = []
    jobs.append(pool.apply_async(ocl_writer_worker, (db_path,)))
    jobs.append(pool.apply_async(ocl_preprocessor_worker, (db_path,)))
    jobs.append(pool.apply_async(ocl_builder_worker, (db_path,)))
    [job.wait() for job in jobs]  # Wait for jobs to finish
    print()  # Print job output
    [print(job.get()) for job in jobs]
    print()

    # Second batch of workers
    jobs = []
    jobs.append(pool.apply_async(bytecode_features_worker, (db_path,)))
    [job.wait() for job in jobs]  # Wait for jobs to finish
    print()  # Print job output
    [print(job.get()) for job in jobs]
    print()

    # Third batch of workers
    jobs = []
    jobs.append(pool.apply_async(ocl_tidy_worker, (db_path,)))
    [job.wait() for job in jobs]  # Wait for jobs to finish
    print()  # Print job output
    [print(job.get()) for job in jobs]

    jobs = []
    jobs.append(pool.apply_async(rewrite_cl_worker, (db_path,)))
    [job.wait() for job in jobs]  # Wait for jobs to finish
    print()  # Print job output
    [print(job.get()) for job in jobs]


if __name__ == '__main__':
    main()
