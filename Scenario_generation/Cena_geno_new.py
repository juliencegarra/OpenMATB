from Session_new import Session

exps = [[0,	1,	5,	2,	4,	3],
        [1,	2,	0,	3,	5,	4],
        [2,	3,	1,	4,	0,	5],
        [3,	4,	2,	5,	1,	0],
        [4,	5,	3,	1,	2,	1],
        [5,	0,	4,	2,	3,	2]] # Balanced Latin Square

i=1
for exp in exps:
    j=0
    for unit in exp:
        sc = Session(list=[unit],length=1,name = 'sc_'+str(i)+'_'+str(j+1),tt=100)
        sc.init()
        sc.sswrite()
        sc.end()
        j+=1
    i+=1