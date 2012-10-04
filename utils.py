import threading
import queue
import time
import random

def _acquire(self, blocking = 1):
    if not hasattr(self, '__object_lock'):
        self.__object_lock = threading.RLock();

    self.__object_lock.acquire(blocking)

def _release(self):
    self.__object_lock.release()
    
def _enter(self):
    self.acquire()
    return self

def _exit(self, type, value, traceback):
    self.release()

def _init(cls, attrs):
    def call_super(self, *args, **kwargs):
        super(eval(cls), self).__init__(*args, **kwargs)

    constructor = attrs.get('__init__', call_super)

    def init(self, *args, **kwargs):
        self.__object_lock = threading.RLock()
        constructor(self, *args, **kwargs)

    return init

class SynchronizedClass(type):
    def __new__(cls, name, bases, attrs):
        #print(name, attrs)
        #attrs['__object_lock'] = threading.RLock()
        #attrs['__init__'] = _init(name, attrs)
        attrs['acquire'] = _acquire
        attrs['release'] = _release
        attrs['__enter__'] = _enter
        attrs['__exit__'] = _exit

        return super(\
            SynchronizedClass, cls).__new__(cls, name, bases, attrs)

class synchronize(object):
    def __init__(self, *names):
        #print('init', names)
        self._names = names

    def __call__(self, base):
        #print('call', base)
        for name in self._names:
            self._each_name(base, name)

        return base

    def _each_name(self, base, name):
        meth = getattr(base, name)
        def wrap(self, *args, **kwargs):
            with self:
                return meth(self, *args, **kwargs)
        setattr(base, name, wrap)

        return base

class SynchronizedList(list, metaclass = SynchronizedClass):
    pass

class TimerTask(threading.Thread):
    def __init__(self):
        super(TimerTask, self).__init__()
        self.daemon = True

        self._arrived = threading.Condition()
        self._queue = queue.PriorityQueue()

        self._halt = False

    def halt(self):
        with self._arrived:
            self._halt = True
            #self.add(self._null_task(0))
            self._queue.put(self._null_task(0))
            self._arrived.notify()

    def run(self):
        while not self._halt:
            task = self._queue.get(True)
            with self._arrived:
                when = task.at - time.time()
                if when <= 0:
                    task()
                else:
                    self._arrived.wait(when)
                    self._queue.put(task)

    # Run the task at 'time'
    def at(self, abs_time, f, *args, **kwargs):
        with self._arrived:
            task = TimerTask.Task(abs_time, f, *args, **kwargs)
            self.add_task(task)

    # Run the task now
    def now(self, f, *args, **kwargs):
        self.then(0, f, *args, **kwargs)

    # Run the task 'time' seconds from now
    def then(self, time, f, *args, **kwargs):
        with self._arrived:
            task = TimerTask.Task.create(time, f, *args, **kwargs)
            self.add_task(task)

    def add_task(self, task):
        with self._arrived:
            self._queue.put(task)
            self._arrived.notify()

    def _null_task(self, from_now):
        def null():
            pass

        return TimerTask.Task(from_now, null)

    class Task(object):
        @classmethod
        def create(cls, from_now, f, *args, **kwargs):
            return cls(time.time() + from_now, f, *args, **kwargs)

        def __init__(self, abs_time, f, *args, **kwargs):
            self._f = f
            self._args = args
            self._kwargs = kwargs
            self._time = abs_time

        @property
        def at(self):
            return self._time

        def __str__(self):
            return "<Task function=%s>" % self._f.__name__

        def __lt__(self, other):
            return self._time < other._time

        def __call__(self):
            return self._f(*self._args, **self._kwargs)


if __name__ == '__main__':
    #t1 = TimerTask.Task(1, lambda x: x)
    #t2 = TimerTask.Task(1, lambda x: x)

    #print(t1 < t2)

    l = SynchronizedList((1,2,3,4,6))
    with l:
        print(l)

    print(l.__object_lock)

    class SC(object):
        def __init__(self):
            self.name = "what"

    class SyncClass(SC, metaclass = SynchronizedClass):
        def n(self):
            return self.name

    
    s = SyncClass()
    with s:
        print(s.name)
        print(s.n())

    s = SynchronizedList()
