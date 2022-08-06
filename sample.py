class Position(object):
    def __init__(self):
        self.qty = 1

class Sample(object):
    def __init__(self):
        self.name='Sample'
    
    def start(self):
        print('start')
        stack = []
        positions = {}
        positions['A'] = {'qty':20}
        pos = positions['A']

        print(positions['A'])
        print(pos)
        pos['qty'] = 1000
        print(positions['A'])
        print(pos)
        a = 2
        b = 3
        print (f'{a} / {b}')

        

           

if __name__ == '__main__':
    trader = Sample()
    trader.start()
