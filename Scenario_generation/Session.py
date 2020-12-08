import random,os

modules = ['track','sysmon','sysmon_right','sysmon_left','scheduling']

wl = [['track;targetradius;0.30','track;cutofffrequency;0.4','track;joystickforce;0.02','track;automaticsolver;False'],
      ['track;targetradius;0.20','track;cutofffrequency;0.7','track;joystickforce;0.02','track;automaticsolver;False']
      ]

almode = [['sysmon_right;lights-1-oncolor;#FF0000','sysmon_right;lights-2-oncolor;#FF0000',
           'sysmon_left;lights-1-oncolor;#FF0000','sysmon_left;lights-2-oncolor;#FF0000'],
          ['sysmon_right;lights-1-oncolor;#FFFF00','sysmon_right;lights-2-oncolor;#FFFF00',
           'sysmon_left;lights-1-oncolor;#FFFF00','sysmon_left;lights-2-oncolor;#FFFF00'],
           ['sysmon_right;lights-1-oncolor;#00FF00','sysmon_right;lights-2-oncolor;#00FF00',
           'sysmon_left;lights-1-oncolor;#00FF00','sysmon_left;lights-2-oncolor;#00FF00']]

lfailure = ['sysmon_left;lights-1-failure;True','sysmon_left;lights-2-failure;True',
           'sysmon_right;lights-1-failure;True','sysmon_right;lights-2-failure;True']

class Session(object):
    def __init__(self, list = [0,1,2,3,4,5], length=6,name='defaut_session',tt=600,):
        self.list = list
        self.length = length
        self.name = name
        self.fic = 0
        self.tt = 600

    def add(self, int):
        self.list.append(int)
        self.length+=1

    def init(self):
        ''' Try to seperate Scenario files
        working_directory = os.getcwd()
        if not os.path.exists(os.path.join(working_directory, LOGS_PATH)):
            os.mkdir(os.path.join(working_directory, LOGS_PATH))
            '''
        self.fic = open('Scenarios\\' + self.name + '.txt', 'w')
        
    def sswrite(self):
        writeparam(self)
        writestart(self)
        writend(self)

    def end(self):
        self.fic.close()

def gettime(t):
    mm = int(t/60)
    ss = int(t%60)
    time = "0:{:0>2d}:{:0>2d};".format(mm,ss)
    return time


      
def writestart(session):
    time = gettime(0)
    for mod in modules:
        message = time + mod +';start\n'
        session.fic.write(message)
    session.fic.write('\n')

def writend(session):
    time = gettime(session.tt)
    for mod in modules:
        message = time + mod +';stop\n'
        session.fic.write(message)
    time = gettime(session.tt+1)
    session.fic.write(time+'end\n') 

def writeparam(session):
    for i in range(session.length):
        writewlp(i,session.list[i],session.fic)
        session.fic.write('\n')
        writemode(i,session.list[i],session.fic)
        session.fic.write('\n')
    genefailure(session.fic)

def writewlp(t,i,fic):
    k = int (i/3)
    for param in wl[k]:
            message = gettime(t*100)+param+'\n'
            fic.write(message)

def writemode(t,i,fic):
    k = int (i%3)
    for param in almode[k]:
            message = gettime(t*100)+param+'\n'
            fic.write(message)

def genefailure(fic):
    q=0
    failurelist = []
    for i in range(24):
        t = random.randint(int(i/4)*100,int(i/4)*100+100)
        lid = random.randint(0,3)
        failurelist.append([t,lid])
    for fail in failurelist:
        time = gettime(fail[0])
        message = time + lfailure[fail[1]] + '\n'
        fic.write(message)
        q+=1
        if q%4 == 0: fic.write('\n')

"""
I want to realise the overlap warming
while something wrong with recursive function
(int out of range 32bit, why??)

def recgef(i,flist,rel):
    t = random.randint(int(i/4)*100,int(i/4)*100+100)
    lid = random.randint(0,3)
    if rel[lid] == 0:
        return recgef(i,flist,rel)
    else:
        if flist == []:
            return t,lid
        else:
            for i in range(len(flist)):
                if flist[i][1] == lid:
                    if t - flist[i][0] < 10:
                        return recgef(i,flist,rel)
                    else: 
                        return t,lid
                else:
                    return t,lid

def genefailure(fic):
    rel = [5]*4
    failurelist = []
    for i in range(24):
        t,lid = recgef(i,failurelist,rel)
        failurelist.append([t,lid])
        rel[lid] -= 1
    for fail in failurelist:
        time = gettime(fail[0])
        message = time + lfailure[fail[1]] + '\n'
        fic.write(message)
"""


