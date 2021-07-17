import random
from lazyops import lazymultiproc, timer


def create_sequences(num_seqs=50000):
    return [random.randint(0, num_seqs) for _ in range(num_seqs)]

@lazymultiproc(dataset_callable=create_sequences, num_procs=4)
def run_seq(n=1):
    return n * 5

if __name__ == '__main__':
    time = timer()
    res = []
    for i in run_seq():
        res.extend(i)

    print('Total Items in Results: ', len(res))
    print('Completed Process in ', time.ablstime)
