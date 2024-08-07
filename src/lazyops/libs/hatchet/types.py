
# https://stackoverflow.com/questions/2352181/how-to-use-a-dot-to-access-members-of-dictionary

from typing import Any, Dict, List, Iterable, Union

class DotDict(dict):
    # https://stackoverflow.com/a/70665030/913098
    """
    Example:
    m = Map({'first_name': 'Eduardo'}, last_name='Pool', age=24, sports=['Soccer'])

    Iterable are assumed to have a constructor taking list as input.
    """

    def __init__(self, *args, **kwargs):
        super(DotDict, self).__init__(*args, **kwargs)

        args_with_kwargs = list(args)
        args_with_kwargs.append(kwargs)
        args = args_with_kwargs

        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v
                    if isinstance(v, dict):
                        self[k] = DotDict(v)
                    elif isinstance(v, (str, bytes)):
                        self[k] = v
                    elif isinstance(v, Iterable):
                        klass = type(v)
                        map_value: List[Any] = []
                        for e in v:
                            map_e = DotDict(e) if isinstance(e, dict) else e
                            map_value.append(map_e)
                        self[k] = klass(map_value)



    def __getattr__(self, attr) -> Union[Dict[str, Any], List[Any], Any]: 
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(DotDict, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(DotDict, self).__delitem__(key)
        del self.__dict__[key]

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__.update(d)
