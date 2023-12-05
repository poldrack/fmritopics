# code to retrieve pubmed abstracts for fMRI per year


import sys
import os
from Bio import Entrez
import time
import pickle
from fmrihandbook.utils.pubmed import get_pubmed_query_results  # noqa: E402
from collections import namedtuple


Entrez.email = 'poldrack@stanford.edu'
end_year = 2022
pmids = {}

datadir = 'data'
if not os.path.exists(datadir):
    os.mkdir(datadir)

pmid_file = os.path.join(datadir, 'fmri_pmids.pkl')

if os.path.exists(pmid_file):
    with open(pmid_file, 'rb') as f:
        pmids = pickle.load(f)
else:

    for year in range(1990, end_year + 1):
        query = '("fMRI" OR "functional MRI" OR "functional magnetic resonance imaging") AND (brain OR neural OR neuroscience OR neurological OR psychiatric OR psychology) AND %d[DP]' % year
        results = get_pubmed_query_results(query, Entrez.email)
        pmids[year] = [int(i) for i in results['IdList']]
        print('found %d records for' % len(pmids[year]), year)
        time.sleep(0.5)
    pickle.dump(pmids, open(pmid_file, 'wb'))

# %% [markdown]
# code to retrieve pubmed abstracts for fMRI per year


# get abstracts for each PMID


maxtries = 5
authors = []

# since different terms have different #s of abstracts,
# only take as many as the minimum
# to prevent different terms from overwhelming the analyses

retmax = max([len(pmids[k]) for k in pmids])

PMID = namedtuple('PMID', ['pmid', 'year', 'abstract'])

if os.path.exists(os.path.join(datadir, 'pmid_records.pkl')):
    pmid_records = pickle.load(
        open(os.path.join(datadir, 'pmid_records.pkl'), 'rb')
    )
else:
    pmid_records = []
    delay = 2
    maxtries = 5

    for year, pmids_year in pmids.items():
        if len(pmids_year) == 0:
            continue
        print('getting records for', year)
        good_record = False
        tries = 0
        while not good_record:
            try:
                handle = Entrez.efetch(
                    db='pubmed',
                    id=','.join(['%d' % i for i in pmids_year]),
                    retmax=retmax,
                    retmode='xml',
                )
                time.sleep(delay)
                records = Entrez.read(handle)
                good_record = True
            except:
                e = sys.exc_info()[0]
                print('retrying', year, e)
                tries += 1
                if tries > maxtries:
                    raise e

        for i in records['PubmedArticle']:
            pmid = int(i['MedlineCitation']['PMID'])
            if 'Abstract' in i['MedlineCitation']['Article']:
                abstract = i['MedlineCitation']['Article'][
                    'Abstract'
                ]['AbstractText'][0]
            else:
                abstract = None
            pmid_records.append(PMID(pmid, year, abstract))

    pickle.dump(pmid_records, open(os.path.join(datadir, 'pmid_records.pkl'), 'wb'))
