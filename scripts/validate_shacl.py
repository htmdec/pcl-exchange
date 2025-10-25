#!/usr/bin/env python3
# Validate a data graph (JSON-LD or Turtle) against one or more SHACL shapes using pyshacl.
import argparse, sys, json, pathlib
from pyshacl import validate
from rdflib import Graph

def load_graph(path):
    p = pathlib.Path(path)
    g = Graph()
    if p.suffix.lower() in ('.json', '.jsonld'):
        g.parse(p.as_posix(), format='json-ld')
    elif p.suffix.lower() in ('.ttl',):
        g.parse(p.as_posix(), format='turtle')
    else:
        # try json-ld by default
        try:
            g.parse(p.as_posix(), format='json-ld')
        except Exception:
            g.parse(p.as_posix(), format='turtle')
    return g

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='Path to JSON-LD/Turtle data file')
    ap.add_argument('--shapes', nargs='+', required=True, help='One or more TTL shape files')
    args = ap.parse_args()

    data_graph = load_graph(args.data)
    shapes_g = Graph()
    for s in args.shapes:
        shapes_g.parse(s, format='turtle')

    conforms, results_graph, results_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_g,
        inference='rdfs',
        abort_on_error=False,
        allow_infos=True,
        allow_warnings=True
    )
    print(results_text)
    if not conforms:
        sys.exit(2)

if __name__ == '__main__':
    main()
