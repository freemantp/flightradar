from flask import request


def get_boolean_arg(argname):
    arch_arg = request.args.get(argname)
    if arch_arg:
        return arch_arg.lower() == 'true'
    else:
        return False