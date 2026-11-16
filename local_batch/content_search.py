"""Local, read-only page search. No inference, downloads or persistent index."""
import difflib
import hashlib
import json
import re
import unicodedata
from pathlib import Path


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(c))


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def parse_query(query, mode):
    if query.count('"') % 2:
        raise ValueError('Cierra las comillas de la frase')
    criteria = []
    for match in re.finditer(r'"([^"\n]+)"|([\w]+)', query):
        label = match.group(1) or match.group(2)
        terms = re.findall(r'\w+', normalize(label))
        if terms and terms not in [c['terms'] for c in criteria]:
            criteria.append(dict(id=len(criteria), label=label, terms=terms,
                                 phrase=bool(match.group(1)), gap=2 if match.group(1) else 0))
    if mode == 'phrase':
        terms = re.findall(r'\w+', normalize(query))
        criteria = [dict(id=0, label=query, terms=terms, phrase=True, gap=0)]
    if not criteria or sum(len(c['terms']) for c in criteria) > 20:
        raise ValueError('Use 1–20 search terms')
    return criteria


def match_text(text, criteria, mode, similarity):
    tokens = list(re.finditer(r'\w+', text))
    words = [normalize(t.group()) for t in tokens]
    found = []
    fuzzy = mode in ('flexible', 'approximate')
    def equal(term, word):
        if term == word:
            return True
        if not fuzzy or min(len(term), len(word)) < 4 or abs(len(term)-len(word)) > 2:
            return False
        key = (term, word)
        if key not in similarity:
            similarity[key] = difflib.SequenceMatcher(None, term, word).ratio() >= .82
        return similarity[key]
    for criterion in criteria:
        terms = criterion['terms']
        spans, approximate = [], False
        for i, word in enumerate(words):
            if not equal(terms[0], word):
                continue
            # Ordered phrase, at most two intervening words TOTAL.
            paths = [(i, [i], 0)]
            for term in terms[1:]:
                next_paths = []
                for last, path, gaps in paths:
                    for j in range(last+1, min(len(words), last+2+criterion['gap']-gaps)):
                        if equal(term, words[j]):
                            next_paths.append((j, path+[j], gaps+j-last-1))
                paths = next_paths
                if not paths:
                    break
            for _, path, _ in paths:
                spans.extend((tokens[j].start(), tokens[j].end()) for j in path)
                approximate |= any(terms[k] != words[j] for k, j in enumerate(path))
        if spans:
            found.append(dict(criterion=criterion['id'], label=criterion['label'],
                              approximate=approximate, offsets=sorted(set(spans))))
    if mode != 'flexible' and len(found) != len(criteria):
        return []
    return found


def search(root, query, mode='flexible', document_id=None, page_number=None, include_text=False):
    query = query.strip()
    if not 2 <= len(query) <= 200 or mode not in ('words', 'phrase', 'approximate', 'flexible'):
        raise ValueError('Use 2–200 characters and a valid search mode')
    criteria = parse_query(query, mode)
    similarity = {}
    docs = read_json(root / 'progress.json').get('documents', [])
    # Only secondary readings tied to a known corpus page are included.
    secondary = {}
    for meta_path in sorted((root / 'second_reading').glob('*/case_*/metadata.json')):
        meta = read_json(meta_path)
        text_path = meta_path.parent / 'transcription.md'
        if text_path.exists():
            secondary.setdefault((meta.get('document'), meta.get('page')), []).append(
                (text_path.read_text(), 'second_reading:' + meta_path.parent.parent.name, 'unreviewed'))
    hits, scanned, missing = [], 0, 0
    for doc in docs:
        output = Path(doc['output']).resolve()
        if not output.is_relative_to((root / 'documents').resolve()):
            continue
        ident = hashlib.sha256(doc['source'].encode()).hexdigest()
        if document_id is not None and ident != document_id:
            continue
        for page in range(1, doc['page_count'] + 1):
            if page_number is not None and page != page_number:
                continue
            path = output / f'page_{page:04}.md'
            original = path.read_text() if path.exists() else ''
            variants = [(original, 'original', 'unreviewed')] if original.strip() else []
            variants += secondary.get((doc['source'], page), [])
            human = read_json(root / 'reviews' / ident / f'{page}.json')
            if human:
                current = human.get('original_hash') == hashlib.sha256(original.encode()).hexdigest()
                variants.insert(0, (human.get('text', ''), 'human', human.get('status', 'draft') if current else 'stale'))
            if not any(text.strip() for text, _, _ in variants):
                missing += 1
                continue
            scanned += 1
            matches = []
            for text, version, status in variants:
                found = match_text(text, criteria, mode, similarity)
                if not found and not include_text:
                    continue
                locations = sorted({tuple(span) for item in found for span in item['offsets']})
                approximate = any(item['approximate'] for item in found)
                # Keep evidence for every query term, even when far apart on the page.
                excerpts = []
                for start, end in locations:
                    if any(a <= start and end <= b for a, b in excerpts):
                        continue
                    excerpts.append((max(0, start-100), min(len(text), end+160)))
                    if len(excerpts) >= 20:
                        break
                matches.append(dict(version=version, status=status, approximate=approximate, criteria=found, text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                                    **({'text': text} if include_text else {}),
                                    excerpts=[dict(text=text[a:b], highlights=[(s-a,e-a) for s,e in locations if a<=s and e<=b]) for a,b in excerpts]))
            if matches:
                hits.append(dict(document=doc['source'], document_id=ident,
                                 folder=doc['folder'], page=page, matches=matches,
                                 matched_criteria=sorted({c['criterion'] for m in matches for c in m['criteria']})))
    hits.sort(key=lambda h: (-len(h['matched_criteria']), all(m['approximate'] for m in h['matches']), h['folder'], h['document'], h['page']))
    return dict(query=query, mode=mode, criteria=criteria, pages_searched=scanned, pages_without_text=missing,
                total_pages=len(hits), documents=len({h['document'] for h in hits}), hits=hits)
