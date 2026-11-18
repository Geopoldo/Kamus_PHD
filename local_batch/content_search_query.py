"""Bounded Boolean query grammar: NOT > AND > OR; adjacent terms imply AND."""
import re

LOGICAL_MODES = ('boolean', 'boolean_approximate')


def parse_boolean(query, normalize):
    tokens = []
    criteria = []
    end = 0
    for match in re.finditer(r'"([^"\n]*)"|([()])|([^\s()"]+)', query):
        if query[end:match.start()].strip():
            raise ValueError('Cierra las comillas y escribe cada frase en una sola línea.')
        end = match.end()
        quoted, bracket, word = match.groups()
        if bracket:
            tokens.append(bracket)
        elif quoted is None and word in ('AND', 'OR', 'NOT'):
            tokens.append(word)
        else:
            label = quoted if quoted is not None else word
            terms = re.findall(r'\w+', normalize(label))
            if not terms:
                raise ValueError('Cada chip debe contener una palabra o una frase.')
            key = (terms, quoted is not None)
            existing = next((c for c in criteria if (c['terms'], c['phrase']) == key), None)
            if existing is None:
                existing = dict(id=len(criteria), label=label, terms=terms,
                                phrase=quoted is not None, gap=2 if quoted is not None else 0)
                criteria.append(existing)
            tokens.append(('term', existing['id']))
    if query[end:].strip():
        raise ValueError('Cierra las comillas y escribe cada frase en una sola línea.')
    if not criteria or sum(len(c['terms']) for c in criteria) > 20 or len(tokens) > 100:
        raise ValueError('Usa entre 1 y 20 términos de búsqueda.')
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else None

    def unary():
        nonlocal position
        token = peek()
        if token == 'NOT':
            position += 1
            return ('not', unary())
        if token == '(':
            position += 1
            result = disjunction()
            if peek() != ')':
                raise ValueError('Falta cerrar un paréntesis.')
            position += 1
            return result
        if isinstance(token, tuple):
            position += 1
            return token
        raise ValueError('Falta una palabra o frase junto al operador lógico.')

    def conjunction():
        nonlocal position
        result = unary()
        while peek() is not None and peek() not in (')', 'OR'):
            if peek() == 'AND':
                position += 1
            result = ('and', result, unary())
        return result

    def disjunction():
        nonlocal position
        result = conjunction()
        while peek() == 'OR':
            position += 1
            result = ('or', result, conjunction())
        return result

    expression = disjunction()
    if position != len(tokens):
        raise ValueError('Hay un paréntesis de cierre sin apertura.')

    def mark(node, negative=False):
        if node[0] == 'term':
            criteria[node[1]]['negative' if negative else 'positive'] = True
        elif node[0] == 'not':
            mark(node[1], not negative)
        else:
            mark(node[1], negative)
            mark(node[2], negative)

    mark(expression)
    return criteria, expression


def evaluate_boolean(expression, present):
    operation = expression[0]
    if operation == 'term':
        return expression[1] in present
    if operation == 'not':
        return not evaluate_boolean(expression[1], present)
    if operation == 'and':
        return evaluate_boolean(expression[1], present) and evaluate_boolean(expression[2], present)
    return evaluate_boolean(expression[1], present) or evaluate_boolean(expression[2], present)
