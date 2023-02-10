from pymsgbox import alert, confirm

def fatalerror(msg):
    alert(text=msg, title=_(f'OpenMATB Error'), button=_('Exit'))
    exit(0)

def errorchoice(msg):
    response = confirm(text=msg, title=_(f'OpenMATB Error'), buttons=[_('Continue'), _('Abort')])
    if response == _('Abort'):
        exit(0)
    elif response == _('Continue'):
        pass
