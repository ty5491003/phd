import json
import os
import re
import sys
import sqlite3

from time import sleep
from functools import partial

import requests

from base64 import b64decode
from github import Github,GithubException
from hashlib import sha1
from subprocess import Popen,PIPE,STDOUT

import smith

# Counters
repos_new_counter = 0
repos_modified_counter = 0
repos_unchanged_counter = 0
files_new_counter = 0
files_modified_counter = 0
files_unchanged_counter = 0
errors_counter = 0
status_string = ''

def print_repo_details(repo):
    print('url:', repo.url)
    print('owner:', repo.owner.email)
    print('name:', repo.name)
    print('fork:', repo.fork)
    print('stars:', repo.stargazers_count)
    print('contributors:', len([x for x in repo.get_contributors()]))
    print('forks:', repo.forks)
    print('created_at:', repo.created_at)
    print('updated_at:', repo.updated_at)


def print_file_details(file):
    print('url:', file.url)
    print('path:', file.path)
    print('sha:', file.sha)
    print('size:', file.size)


def print_counters():
    print('\r\033[Kfiles: new ', files_new_counter,
          ', modified ', files_modified_counter,
          ', unchanged ', files_unchanged_counter,
          '. repos: new ', repos_new_counter,
          ', modified ', repos_modified_counter,
          ', unchanged ', repos_unchanged_counter,
          '. errors ', errors_counter,
          '. current: ', status_string[0:25],
          sep='', end='')
    sys.stdout.flush()


def rate_limit(g):
    global status_string
    remaining = g.get_rate_limit().rate.remaining
    while remaining < 100:
        sleep(1)
        status_string = 'WAITING ON RATE LIMIT'
        print_counters()
        remaining = g.get_rate_limit().rate.remaining


def process_repo(g, db, repo):
    global repos_new_counter,repos_modified_counter,repos_unchanged_counter
    global status_string

    rate_limit(g)
    url = repo.url
    updated_at = str(repo.updated_at)
    name = repo.name
    status_string = name
    print_counters()

    c = db.cursor()
    c.execute("SELECT updated_at FROM Repositories WHERE url=?", (url,))
    cached_updated_at = c.fetchone()

    # Do nothing unless updated timestamps don't match
    if cached_updated_at and cached_updated_at[0] == updated_at:
        repos_unchanged_counter += 1
        return False

    owner = repo.owner.email
    fork = 1 if repo.fork else 0
    stars = repo.stargazers_count
    try:
        contributors = len([x for x in repo.get_contributors()])
    except GithubException as e:
        contributors = -1
    forks = repo.forks
    created_at = repo.created_at
    updated_at = repo.updated_at

    c.execute("DELETE FROM Repositories WHERE url=?", (url,))
    c.execute("INSERT INTO Repositories VALUES(?,?,?,?,?,?,?,?,?)",
              (url, owner, name, fork, stars, contributors, forks, created_at,
               updated_at))

    if cached_updated_at:
        repos_modified_counter += 1
    else:
        repos_new_counter += 1
    db.commit()
    return True


def is_opencl_path(path):
    return path.endswith('.cl') or path.endswith('.ocl')

_include_re = re.compile('\w*#include ["<](.*)[">]')

def download_file(github_token, repo, url, stack):
    # Recursion stack
    stack.append(url)

    response = json.loads(requests.get(
        url,
        headers = {
            'Authorization': 'token ' + str(github_token)
        }
    ).content.decode('utf-8'))
    src = b64decode(response['content']).decode('utf-8')

    outlines = []
    for line in src.split('\n'):
        match = re.match(_include_re, line)
        if match:
            include_name = match.group(1)

            # Try and resolve relative paths
            include_name = include_name.replace('../', '')

            branch = repo.default_branch
            tree_iterator = repo.get_git_tree(branch, recursive=True).tree
            include_url = ''
            for f in tree_iterator:
                if f.path.endswith(include_name):
                    include_url = f.url
                    break

            if include_url and include_url not in stack:
                include_src = download_file(github_token, repo, include_url)
                outlines.append(include_src)
            else:
                if not include_url:
                    outlines.append('// [FETCH] didnt find: ' + line)
                else:
                    outlines.append('// [FETCH] skipped: ' + line)
        else:
            outlines.append(line)

    return '\n'.join(outlines)


def process_file(g, github_token, db, repo, file):
    global files_new_counter,files_modified_counter,files_unchanged_counter
    global status_string

    # rate_limit(g)

    # We're only interested in OpenCL files.
    if not is_opencl_path(file.path):
        return

    url = file.url
    sha = file.sha
    path = file.path
    status_string = repo.name + '/' + path
    print_counters()

    c = db.cursor()
    c.execute("SELECT sha FROM ContentMeta WHERE id=?", (url,))
    cached_sha = c.fetchone()

    # Do nothing unless checksums don't match
    if cached_sha and cached_sha[0] == sha:
        files_unchanged_counter += 1
        return False

    repo_url = repo.url
    contents = download_file(github_token, repo, file.url, [])
    size = file.size

    c.execute("DELETE FROM ContentFiles WHERE id=?", (url,))
    c.execute("DELETE FROM ContentMeta WHERE id=?", (url,))
    c.execute("INSERT INTO ContentFiles VALUES(?,?)",
              (url, contents))
    c.execute("INSERT INTO ContentMeta VALUES(?,?,?,?,?)",
              (url, path, repo_url, sha, size))

    if cached_sha:
        files_modified_counter += 1
    else:
        files_new_counter += 1

    db.commit()
    return True

# Download all of the OpenCL on GitHub (!)
#
# Shortcomings of this appraoch:
#
#   Only includes 'actual' OpenCL files, no inline strings
def github(db_path, github_username, github_pw, github_token):
    global errors_counter

    g = Github(github_username, github_pw)
    db = sqlite3.connect(db_path)
    handle_repo = partial(process_repo, g, db)
    # TODO: Verify tables have been created

    # Fetch the repositories to iterate over. Since opencl isn't
    # treated as a first-class language by GitHub, we can't use the
    # 'language=' keyword for queries, so instead we through a much
    # wider net and filter the results afterwards.
    #
    query_terms = [
        'opencl',
        'cl',
        'khronos',
        'gpu',
        'gpgpu',
        'cuda',
        'amd',
        'nvidia',
        'heterogeneous'
    ]
    for query in query_terms:
        repos = g.search_repositories(query + ' fork:true sort:stars')

        for repo in repos:
            repo_modified = handle_repo(repo)

            # Do nothing unless the repo is new / modified
            if not repo_modified:
                continue

            handle_file = partial(process_file, g, github_token, db, repo)

            # Iterate over the entire git tree of the repo's default
            # branch (usually 'master'). If a file ends with the .cl
            # extension, check to see if we already have it, else download
            # it.
            #
            try:
                branch = repo.default_branch
                tree_iterator = repo.get_git_tree(branch, recursive=True).tree
                for f in tree_iterator:
                    try:
                        handle_file(f)
                    except Exception as e:
                        errors_counter += 1
            except GithubException as e:
                # Do nothing in case of error (such as an empty repo)
                pass

    print_counters()
    print("\n\ndone.")
    db.close()


_include_re = re.compile('\w*#include ["<](.*)[">]')
_parboil_re = re.compile('.+/benchmarks/parboil/benchmarks/(.+)/src/opencl_base/(.+\.cl)')


def get_path_id(path):
    match = re.match(_parboil_re, path)
    if match:
        return match.group(1) + '-' + match.group(2)
    else:
        return path


def inline_headers(path, stack):
    stack.append(path)

    with open(path) as infile:
        src = infile.read()

    outlines = []
    for line in src.split('\n'):
        match = re.match(_include_re, line)
        if match:
            include_name = match.group(1)

            # Try and resolve relative paths
            include_name = include_name.replace('../', '')

            include_path = os.path.join(os.path.dirname(path), include_name)

            if os.path.exists(include_path) and include_path not in stack:
                include_src = inline_headers(include_path, stack)
                outlines.append('// [FETCH] include: ' + include_path)
                outlines.append(include_src)
                outlines.append('// [FETCH] eof(' + include_path + ')')
            else:
                if include_path in stack:
                    outlines.append('// [FETCH] ignored recursive include: ' + include_path)
                else:
                    outlines.append('// [FETCH] 404 not found: ' + include_path)
        else:
            outlines.append(line)

    return '\n'.join(outlines)


def is_opencl_path(path):
    return path.endswith('.cl') or path.endswith('.ocl')


def flatten(l):
    return [item for sublist in l for item in sublist]


def process_cl_file(db_path, path):
    """
    :param db_path: Path to output database.
    :param path: Path to input file.
    """
    db = sqlite3.connect(db_path)
    c = db.cursor()

    contents = inline_headers(path, [])
    id = get_path_id(path)
    print(id)
    c.execute('INSERT OR IGNORE INTO ContentFiles VALUES(?,?)', (id,contents))

    db.commit()
    c.close()


def content_db(db_path, in_db_path, table='PreprocessedFiles'):
    odb = sqlite3.connect(db_path)
    idb = sqlite3.connect(in_db_path)
    ic = idb.cursor()

    ic.execute('SELECT id,contents FROM {}'.format(table))
    rows = ic.fetchall()

    for id,contents in rows:
        kernels = get_cl_kernels(contents)
        ids = [smith.checksum_str(kernel) for kernel in kernels]
        # print("{} kernels in {}".format(len(kernels), id))
        for kid,kernel in zip(ids, kernels):
            oc = odb.cursor()
            oc.execute('INSERT OR IGNORE INTO ContentFiles VALUES(?,?)',
                       (kid,kernel))
            odb.commit()


def fs(db_path, paths=[]):
    for path in paths:
        process_cl_file(db_path, path)

    print("\r\033[K\ndone.")


# Counters
kernel_counter = 0


def get_cl_kernel(s, start_idx):
    global kernel_counter
    kernel_counter += 1
    print('\r\033[Kkernel:', kernel_counter, end='')
    sys.stdout.flush()

    i = s.find('{', start_idx) + 1
    d = 1  # depth
    while i < len(s) and d > 0:
        if s[i] == '{':
            d += 1
        elif s[i] == '}':
            d -= 1
        i += 1

    return s[start_idx:i]


def get_cl_kernels(s):
    idxs = smith.get_substring_idxs('__kernel void ', s)
    print('extracting', len(idxs), 'kernels ...')
    kernels = [get_cl_kernel(s, i) for i in idxs]
    print()
    return kernels


def process_sample_file(db_path, sample_path, first_only=False):
    db = sqlite3.connect(db_path)
    c = db.cursor()

    with open(sample_path) as infile:
        sample = infile.read()
        if first_only:
            # If first_only argument is set, then only extract a
            # kernel starting at the beginning of the file.
            #
            kernels = [get_cl_kernel(sample, 0)]
        else:
            kernels = get_cl_kernels(sample)

    ids = [smith.checksum_str(kernel) for kernel in kernels]

    for id,kernel in zip(ids, kernels):
        c.execute('INSERT OR IGNORE INTO ContentFiles VALUES(?,?)',
                  (id,kernel))
    db.commit()
    c.close()


def dnn(db_path, samples_dir, sample_path, first_only):
    if samples_dir:
        files = [os.path.join(samples_dir, f) for f in os.listdir(samples_dir)
                 if os.path.isfile(os.path.join(samples_dir, f))]
        for sample_path in files:
            process_sample_file(db_path, sample_path, first_only=first_only)
    else:
        process_sample_file(db_path, sample_path, first_only=first_only)

    print("\r\033[K\ndone.")


# Counters
files_new_counter = 0
errors_counter = 0


class CLSmithException(smith.SmithException): pass
class HeaderNotFoundException(smith.SmithException): pass


def print_counters():
    print('\r\033[Kfiles: new ', files_new_counter,
          '. errors ', errors_counter,
          sep='', end='')
    sys.stdout.flush()


_include_re = re.compile('\w*#include ["<](.*)[">]')


def include_path(name):
    dirs = ('~/phd/extern/clsmith/runtime',
            '~/phd/extern/clsmith/build')
    for dir in dirs:
        path = os.path.join(os.path.expanduser(dir), name)
        if os.path.exists(path):
            return path
    raise HeaderNotFoundException(name)


def inline_headers(src):
    outlines = []
    for line in src.split('\n'):
        match = re.match(_include_re, line)
        if match:
            include_name = match.group(1)

            path = include_path(include_name)
            with open(path) as infile:
                header = infile.read()
                outlines.append(inline_headers(header))
        else:
            outlines.append(line)

    return '\n'.join(outlines)


def get_new_program(db_path):
    global files_new_counter

    clsmith = os.path.expanduser('~/phd/extern/clsmith/build/CLSmith')
    outputpath = 'CLProg.c'

    db = sqlite3.connect(db_path)
    c = db.cursor()

    cmd = [clsmith]

    process = Popen(cmd)
    process.communicate()

    if process.returncode != 0:
        raise CLSmithException()

    with open(outputpath) as infile:
        contents = infile.read()

    contents = inline_headers(contents)

    sha = sha1(contents.encode('utf-8')).hexdigest()

    c.execute('INSERT INTO ContentFiles VALUES(?,?)',
              (sha, contents))
    db.commit()
    db.close()
    files_new_counter += 1
    print_counters()


def clsmith(db_path, target_num_kernels):
    global errors_counter

    print('generating', args.n, 'kernels to', args.input)

    db = sqlite3.connect(db_path)
    c = db.cursor()
    c.execute('SELECT Count(*) FROM ContentFiles')
    num_kernels = c.fetchone()[0]
    while num_kernels < target_num_kernels:
        get_new_program(db_path)
        c.execute('SELECT Count(*) FROM ContentFiles')
        num_kernels = c.fetchone()[0]

    print_counters()
    print("\n\ndone.")
    db.close()


if __name__ == '__main__':
    main()
