from Session import Session

exps = [[0,	1,	5,	2,	4,	3],
        [1,	2,	0,	3,	5,	4],
        [2,	3,	1,	4,	0,	5],
        [3,	4,	2,	5,	1,	0],
        [4,	5,	3,	1,	2,	1],
        [5,	0,	4,	2,	3,	2]] # Balanced Latin Square

for exp in exps:
    sc = Session(list=exp,length=6,name = 'sc_'+str(exp[0]))
    sc.init()
    sc.sswrite()
    sc.end()