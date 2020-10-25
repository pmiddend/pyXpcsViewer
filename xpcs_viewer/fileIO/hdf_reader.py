import h5py
import os
import numpy as np
from multiprocessing import Pool
import time
import json
import logging


logger = logging.getLogger(__name__)


# choose aps 8idi data format
key_fname = 'configure/aps_8idi.json'
with open(key_fname) as f:
    hdf_key = json.load(f)


def put(save_path, fields, result, mode='raw'):
    with h5py.File(save_path, 'a') as f:
        for key in fields:
            if mode == 'alias':
                key2 = hdf_key[key]
            else:
                key2 = key
            if key2 in f:
                del f[key2]
            f[key2] = result[key]
        return


def get(fname, fields_raw, mode='raw', ret_type='dict'):
    """
    get the values for the various keys listed in fields for a single
    file;
    :param fname:
    :param fields_raw: list of keys [key1, key2, ..., ]
    :param mode: ['raw' | 'alias']; alias is defined in .hdf_key
                 otherwise the raw hdf key will be used
    :param ret_type: return dictonary if 'dict', list if it is 'list'
    :return: dictionary or dictionary;
    """
    ret = {}

    # python will modify mutable lists;
    fields = fields_raw.copy()
    fields_org = fields.copy()
    flag = False
    # t_el is not defined in the HDF keys; t_el = t0 * tau
    if 't_el' in fields:
        flag = True
        fields.remove('t_el')
        fields += ['t0', 'tau']

    with h5py.File(fname, 'r') as HDF_Result:
        for key in fields:
            if mode == 'alias':
                key2 = hdf_key[key]
            elif mode == 'raw':
                key2 = key
            else:
                raise ValueError("mode not supported.")

            if key2 not in HDF_Result:
                val = None
            elif 'C2T_all' in key2:
                # C2T_allxxx has to be converted by numpy.array
                val = np.array(HDF_Result.get(key2))
            else:
                val = HDF_Result.get(key2)[()]

            if type(val) == np.ndarray:
                # get rid of length=1 axies;
                val = np.squeeze(val)
            elif type(val) in [np.bytes_, bytes]:
                # converts bytes to unicode;
                val = val.decode()
            ret[key] = val

    if flag:
        ret['t_el'] = ret['t0'] * ret['tau']

    if ret_type == 'dict':
        return ret
    elif ret_type == 'list':
        return [ret[key] for key in fields_org]
    else:
        raise TypeError('ret_type not support')


def get_type(fname):
    ret = get(fname, ['type'], mode='alias')['type']
    return ret.capitalize()


class XpcsFile(object):
    def __init__(self, fname, cwd='../../data'):

        self.full_path = os.path.join(cwd, fname)
        self.cwd = cwd

        self.type = get_type(self.full_path)
        attr = self.load()
        self.__dict__.update(attr)

    def __str2__(self):
        ans = ['File:' + str(self.full_path)]
        for key, val in self.__dict__.items():
            if isinstance(val, np.ndarray) and val.size > 1:
                val = str(val.shape)
            else:
                val = str(val)
            ans.append(f"   {key.ljust(12)}: {val.ljust(30)}")

        return '\n'.join(ans)
    
    def __str__(self):
        ans = ['File:' + str(self.full_path)]
        for key, val in self.__dict__.items():
            if key == 'hdf_key':
                continue
            elif isinstance(val, np.ndarray) and val.size > 1:
                val = str(val.shape)
            else:
                val = str(val)
            ans.append(f"   {key.ljust(12)}: {val.ljust(30)}")

        return '\n'.join(ans)

    def __add__(self, other):
        pass
    
    def load(self, labels=None):
        if self.type == 'Twotime':
            labels = ['saxs_2d', "saxs_1d", 'Iqp', 'ql_sta', 'Int_t', 't0',
                      't1', 'ql_dyn', 'g2_full', 'g2_partials', 'type']
        else:
            labels = ['saxs_2d', "saxs_1d", 'Iqp', 'ql_sta', 'Int_t', 't0',
                      't1', 't_el', 'ql_dyn', 'g2', 'g2_err', 'type']

        ret = get(self.full_path, labels, 'alias')
        return ret
    
    def at(self, key):
        return self.__dict__[key]


def test1():
    # XpcsFile._cwd = '../../data'
    af = XpcsFile(fname='N077_D100_att02_0128_0001-100000.hdf')
    # af = XpcsFile(path='A178_SMB_C_BR_Hetero_SI35_att0_Lq0_001_0001-0768_Twotime.hdf')
    print(af)
    print(af.getattr('saxs_2d'))


if __name__ == '__main__':
    test1()
