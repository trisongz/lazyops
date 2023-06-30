import time
from lazyops.utils.helpers import fail_after

def blocking_func():
    while True:
        print("blocking")
        time.sleep(1)

def test_func():

    try:
        with fail_after(5):
            blocking_func()
    
    except Exception as e:
        print(e)

    print("done")


if __name__ == "__main__":
    test_func()

