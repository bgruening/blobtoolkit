#!/usr/bin/env python3

# pylint: disable=no-member, too-many-branches, too-many-nested-blocks

"""
Add data to a BlobDir.

Usage:
    blobtools add [--bed BED...] [--beddir DIRECTORY]
                  [--busco TSV...] [--cov BAM...] [--hits TSV...] [--fasta FASTA] [--hits-cols LIST]
                  [--key path=value...] [--link path=url...] [--taxid INT] [--skip-link-test]
                  [--blobdb JSON] [--meta YAML] [--synonyms TSV...] [--trnascan TSV...]
                  [--text TXT...] [--text-delimiter STRING] [--text-cols LIST] [--text-header]
                  [--text-no-array] [--taxdump DIRECTORY] [--taxrule bestsum|bestsumorder[=prefix]]
                  [--threads INT] [--evalue NUMBER] [--bitscore NUMBER] [--hit-count INT]
                  [--pileup-args key=value...] [--create] [--replace] DIRECTORY

Arguments:
    DIRECTORY             Existing Blob directory.

Options:
    --bed BED             BED format file.
    --beddir DIRECTORY    Directory containing one or more BED format files.
    --busco TSV           BUSCO full_table.tsv output file.
    --cov BAM             BAM/SAM/CRAM read alignment file.
    --fasta FASTA         FASTA sequence file.
    --hits TSV            Tabular BLAST/Diamond output file.
    --hits-cols LIST      Comma separated list of <column number>=<field name>.
                          [Default: 1=qseqid,2=staxids,3=bitscore,5=sseqid,10=sstart,11=send,14=evalue]
    --taxid INT           Add ranks to metadata for a taxid.
    --key path=value      Set a metadata key to value.
    --link path=URL       Link to an external resource.
    --skip-link-test      Skip test to see if link URL can be resolved.
    --meta YAML           Dataset metadata.
    --blobdb JSON         Blobtools v1 blobDB.
    --synonyms TSV        TSV file containing current identifiers and synonyms.
    --taxdump DIRECTORY   Location of NCBI new_taxdump directory.
    --taxrule rulename[=prefix]
                          Rule to use when assigning BLAST hits to taxa (bestsum, bestsumorder,
                          bestdistsum, bestdistsumorder, blastp).
                          An alternate prefix may be specified. [Default: bestsumorder]
    --threads INT         Number of threads to use for multithreaded tasks. [Default: 1]
    --evalue FLOAT        Set evalue cutoff when parsing hits file. [Default: 1]
    --bitscore FLOAT      Set bitscore cutoff when parsing hits file. [Default: 1]
    --hit-count INT       Number of hits to parse when inferring taxonomy. [Default: 10]
    --text TXT            Generic text file.
    --text-delimiter STRING
                          Text file delimiter. [Default: whitespace]
    --text-cols LIST      Comma separated list of <column number>[=<field name>].
    --text-header         Flag to indicate first row of text file contains field names.
    --text-no-array       Flag to prevent fields in files with duplicate identifiers being
                          loaded as array fields.
    --trnascan TSV        tRNAscan2-SE output
    --pileup-args key=val Key/value pairs to pass to samtools pileup.
    --create              Create a new BlobDir.
    --replace             Replace existing fields with matching ids.

Examples:
    # 1. Add BUSCO scores to BlobDir
    ./blobtools add --busco busco.full_table.tsv BlobDir

"""

import sys

from docopt import docopt

import bed
import blob_db
import busco
import cov
import fasta
import file_io
import hits
import key
import link
import synonyms
import taxid
import text
import trnascan
from fetch import fetch_field, fetch_metadata, fetch_taxdump
from field import Identifier

FIELDS = [
    {"flag": "--bed", "module": bed, "optional": ["identifiers"]},
    {"flag": "--beddir", "module": bed, "optional": ["identifiers"]},
    {"flag": "--fasta", "module": fasta, "optional": ["identifiers"]},
    {"flag": "--blobdb", "module": blob_db, "depends": ["identifiers"]},
    {"flag": "--busco", "module": busco, "depends": ["identifiers"]},
    {"flag": "--text", "module": text, "depends": ["identifiers"]},
    {"flag": "--trnascan", "module": trnascan, "depends": ["identifiers"]},
    {"flag": "--cov", "module": cov, "depends": ["identifiers", "length", "ncount"]},
    {"flag": "--hits", "module": hits, "depends": ["identifiers", "length"]},
    {"flag": "--synonyms", "module": synonyms, "depends": ["identifiers"]},
]
PARAMS = set(
    ["--taxrule", "--threads", "--pileup-args", "--evalue", "--bitscore", "--hit-count"]
)


def has_field_warning(meta, field_id):
    """Warn if dataset has existing field with same id."""
    if meta.has_field(field_id):
        print(
            "WARN: Field '%s' is already present in dataset, not overwriting."
            % field_id
        )
        print("WARN: Use '--replace' flag to overwrite existing field.")
        return 1
    return 0


def main():
    """Entrypoint for blobtools add."""
    args = docopt(__doc__)
    meta = fetch_metadata(args["DIRECTORY"], **args)
    if args["--fasta"]:
        meta.assembly.update({"file": args["--fasta"]})
    taxdump = None
    dependencies = {}
    for field in FIELDS:
        if args[field["flag"]]:
            if "depends" in field:
                for dep in field["depends"]:
                    if dep not in dependencies or not dependencies[dep]:
                        dependencies[dep] = fetch_field(args["DIRECTORY"], dep, meta)
            for dep_key, dep_value in dependencies.items():
                if not dep_value:
                    print("ERROR: '%s.json' was not found in the BlobDir." % dep_key)
                    print(
                        "ERROR: You may need to rebuild the BlobDir to run this command."
                    )
                    sys.exit(1)
            if field["flag"] == "--hits":
                if not taxdump:
                    taxdump = fetch_taxdump(args["--taxdump"])
            parents = field["module"].parent()
            if "optional" in field:
                for dep in field["optional"]:
                    if dep not in dependencies or not dependencies[dep]:
                        dependencies[dep] = fetch_field(args["DIRECTORY"], dep, meta)
            parsed = field["module"].parse(
                args[field["flag"]],
                **{key: args[key] for key in args.keys()},
                taxdump=taxdump,
                dependencies=dependencies,
                meta=meta
            )
            if not isinstance(parsed, list):
                parsed = [parsed]
            for data in parsed:
                if not args["--replace"]:
                    if has_field_warning(meta, data.field_id):
                        continue
                for parent in data.parents:
                    if "range" in parent:
                        parent_meta = meta.field_meta(parent["id"])
                        if parent_meta and "range" in parent_meta:
                            parent["range"][0] = min(
                                parent["range"][0], parent_meta["range"][0]
                            )
                            parent["range"][1] = max(
                                parent["range"][1], parent_meta["range"][1]
                            )
                meta.add_field(parents + data.parents, **data.meta)
                if isinstance(data, Identifier):
                    meta.records = len(data.values)
                json_file = "%s/%s.json" % (args["DIRECTORY"], data.field_id)
                file_io.write_file(json_file, data.values_to_dict())
                dependencies[data.field_id] = data
    if "identifiers" not in dependencies:
        dependencies["identifiers"] = fetch_field(
            args["DIRECTORY"], "identifiers", meta
        )
    for string in args["--link"]:
        link.add(
            string, meta, dependencies["identifiers"].values, args["--skip-link-test"]
        )
    for string in args["--key"]:
        key.add(string, meta, args["--replace"])
    if args["--taxid"]:
        if not taxdump:
            taxdump = fetch_taxdump(args["--taxdump"])
        taxid.add(args["--taxid"], taxdump, meta)
    file_io.write_file("%s/meta.json" % args["DIRECTORY"], meta.to_dict())


if __name__ == "__main__":
    main()
