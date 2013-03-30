import re

_precedence = {'^': 4,
               '*': 2,
               '/': 2,
               '+': 1,
               '-': 1,
               'N': 4}
#_rightAssoc = ['N']
_rightAssoc = ['^', 'N']
_tokens = r'(?:\d+\.?\d*)|(?:\.\d+)|[\^*/+\-()]'
    
    
def safeExp(L):
    b = L.pop()
    a = L.pop()
    if abs(b) > 10:
        raise ValueError("Power too large")
    return a ** b    

_operators = {'*': lambda L: L.pop()*L.pop(),
              '/': lambda L: float(L.pop(-2))/L.pop(),
              '+': lambda L: L.pop()+L.pop(),
              '-': lambda L: L.pop(-2)-L.pop(),
              'N': lambda L: -L.pop(),
              '^': safeExp}


def tokenize(expr):
    return re.findall(_tokens, expr)

def infixToRpn(tokens, verbose):
    # find unary negative signs
    newTokens = []
    for idx in range(len(tokens)):
        if tokens[idx] == "-":
            if idx == 0:
                #newTokens.extend(['0', '-'])
                newTokens.append('N')
            elif tokens[idx-1] in _precedence or tokens[idx-1] == '(':
                #newTokens.extend(['0', '-'])
                newTokens.append('N')
            else:
                newTokens.append('-')
        else:
            newTokens.append(tokens[idx])
    
    if verbose:
        print("Tokens: {}".format(' '.join(newTokens)))
    tokenList = [item for item in reversed(newTokens)]
    output = []
    stack = []
    
    while tokenList:
        token = tokenList.pop()
        if verbose:
            print("Token: {}".format(token))
        if re.search(r'^(\d+\.?\d*)|(\.\d+)$', token) is not None:
            try:
                output.append(int(token))
            except ValueError:
                output.append(float(token))
                if verbose:
                    print("Added to output. O={}, S={}".format(output, stack))
        elif token in _precedence:
            while (stack and stack[-1] != "(" and
                   ((token not in _rightAssoc and 
                    _precedence[token] <= _precedence[stack[-1]]) or 
                   (_precedence[token] <  _precedence[stack[-1]]))):
                output.append(stack.pop())
            stack.append(token)
            if verbose:
                print("Added to stack. O={}, S={}".format(output, stack))
        elif token == "(":
            stack.append(token)
            if verbose:
                print("Added to stack. O={}, S={}".format(output, stack))
        elif token == ")":
            while stack and stack[-1] != "(":
                output.append(stack.pop())
                if verbose:
                    print("Popped stack. O={}, S={}".format(output, stack))
            if not stack:
                raise ValueError("Unmatched parentheses")
            stack.pop()
            if verbose:
                print("Popped '('. O={}, S={}".format(output, stack))
        else:
            raise ValueError("Invalid token")
    
    while stack:
        token = stack.pop()
        if token == "(":
            raise ValueError("Unmatched parentheses")
        output.append(token)
        if verbose:
            print("Popping stack. O={}, S={}".format(output, stack))
    return output

def evalRpn(tokens, verbose=False):
    stack = []

    if verbose:
        print("Evaluating tokens: {}".format(tokens))
    while tokens:
        if verbose:
            print("Tokens={}, stack={}".format(tokens, stack))
        token = tokens.pop(0)
        if verbose:
            print(token)
        if token in _operators:
            stack.append(_operators[token](stack))
        else:
            stack.append(token)
    
    if len(stack) != 1:
        raise ValueError("Invalid tokenization")
    return stack[0]
    
def evalInfix(expr, verbose=False):
    try:
        expr = expr.replace(" ", "")
        if verbose:
            print("Evaluating {}".format(expr))
        tokens = tokenize(expr)
        if ''.join(tokens) != expr:
            if verbose:
                print(tokens)
            raise ValueError("Invalid token detected")
        rpn = infixToRpn(tokens, verbose)
        if verbose:
            print("RPN: {}".format(rpn))
        val = evalRpn(rpn, verbose)
        if verbose:
            print("Value: {}".format(val))
        return val
    except IndexError:
        raise ValueError("Unbalanced expression")

if __name__ == "__main__":
    while True:
        s = raw_input(">")
        evalInfix(s, True)
    
    