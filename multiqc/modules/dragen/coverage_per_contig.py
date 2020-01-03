#!/usr/bin/env python
from __future__ import print_function

import itertools
import math
import re
from collections import OrderedDict, defaultdict
from multiqc.modules.base_module import BaseMultiqcModule
from multiqc.plots import linegraph, bargraph

# Initialise the logger
import logging
log = logging.getLogger(__name__)


class DragenCoveragePerContig(BaseMultiqcModule):
    def parse_coverage_per_contig(self):
        perchrom_data_by_phenotype_by_sample = defaultdict(dict)

        for f in self.find_log_files('dragen/wgs_contig_mean_cov'):
            perchrom_data_by_phenotype = parse_wgs_contig_mean_cov(f)
            if f['s_name'] in perchrom_data_by_phenotype_by_sample:
                log.debug('Duplicate sample name found! Overwriting: {}'.format(f['s_name']))
            self.add_data_source(f, section='stats')
            perchrom_data_by_phenotype_by_sample[f['s_name']].update(perchrom_data_by_phenotype)

        # Filter to strip out ignored sample names:
        perchrom_data_by_phenotype_by_sample = self.ignore_samples(perchrom_data_by_phenotype_by_sample)

        # Merge tumor and normal data:
        perchrom_data_by_sample = defaultdict(dict)
        for sn in perchrom_data_by_phenotype_by_sample:
            for phenotype in perchrom_data_by_phenotype_by_sample[sn]:
                new_sn = sn
                if phenotype == 'normal':
                    new_sn = sn + ' normal'
                perchrom_data_by_sample[new_sn] = perchrom_data_by_phenotype_by_sample[sn][phenotype]

        if not perchrom_data_by_sample:
            return
        log.info('Found Dragen per-contig coverage histogram for {} Dragen output prefixes'.format(
            len(perchrom_data_by_sample)))

        self.add_section(
            name='Coverage per contig',
            anchor='dragen-coverage-per-contig',
            description='Average coverage per contig or chromosome. Calculated as the number of bases (excluding '
                        'duplicate marked reads, reads with MAPQ=0, and clipped bases), divided by '
                        'the length of the contig or (if a target bed is used) the total length of the target '
                        'region spanning that contig.',
            plot=linegraph.plot(perchrom_data_by_sample, pconfig={
                'id': 'dragen_coverage_per_contig',
                'title': 'Average coverage per contig or chromosome',
                'ylab': 'Average coverage',
                'xlab': 'Region',
                'categories': True,
                'tt_label': '<b>{point.x}</b>: {point.y:.1f}x',
            })
        )


def parse_wgs_contig_mean_cov(f):
    """
    The Contig Mean Coverage report generates a _contig_mean_cov.csv file, which contains the estimated coverage for
    all contigs, and an autosomal estimated coverage. The file includes the following three columns

    1. Contig name
    2. Number of bases aligned to that contig, which excludes bases from duplicate marked reads, reads with MAPQ=0,
       and clipped bases.
    3. Estimated coverage, as follows: <number of bases aligned to the contig (ie, Col2)> divided by <length of the
       contig or (if a target bed is used) the total length of the target region spanning that contig>.

    T_SRR7890936_50pc.wgs_contig_mean_cov_normal.csv
    T_SRR7890936_50pc.wgs_contig_mean_cov_tumor.csv

    chr1,11292297134,48.9945
    chr10,6482885699,48.6473
    ...
    chrUn_GL000218v1,20750824,128.77
    chrX,3590295769,23.1792
    chrY,42229820,1.5987
    chrY_KI270740v1_random,0,0
    Autosomal regions ,130912665915,47.4953

    A histogram or a plot like in mosdepth, with each chrom in X axis
    """

    perchrom_data = dict()

    for line in f['f'].splitlines():
        chrom, bases, depth = line.split(',')
        chrom = chrom.strip()
        depth = float(depth)
        # skipping unplaced and alternative contigs, as well as the mitochondria (might attract 100 times more coverage
        # than human chromosomes):
        if chrom.startswith('chrUn_') or chrom.endswith('_random') or chrom.endswith('_alt') \
                or chrom == 'chrM' or chrom == 'MT':
            continue
        perchrom_data[chrom] = depth

    def chrom_order(chrom):
        if chrom == 'Autosomal regions':
            # "Autosomal regions" average coverage goes right after all the autosomal chromosomes
            return 0
        try:
            # autosomal chromosomes go first, thus getting a negative order
            return int(chrom.replace('chr', '')) - len(perchrom_data)
        except ValueError:
            # sex and other chromosomes go in the end
            return 1

    perchrom_data = OrderedDict(sorted(perchrom_data.items(), key=lambda key_val: chrom_order(key_val[0])))

    m = re.search(r'(.*).wgs_contig_mean_cov_(\S*).csv', f['fn'])
    sample, phenotype = m.group(1), m.group(2)
    f['s_name'] = sample
    return {phenotype: perchrom_data}














