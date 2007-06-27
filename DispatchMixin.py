#!/usr/bin/env python
import os,sys,re,inspect

class DispatchMixin:
    """Makes any class callable from the command line. Use like so:

    Test.__bases__ += (DispatchMixin,)
    t = Test()
    t.dispatch()

Note that your class cannot have a method called `dispatch`.
    """

    def Dispatch(self,argv):
        if len(argv) < 2:
            print "No command argument given"
            self.__printValidCommands()
            return
    
        cmd = argv[1]
        if not hasattr(self,cmd):
            print "%s not a valid command" % cmd
            self.__printValidCommands()
            return
    
        func = getattr(self,cmd)
        # lots of futzing to get default argument handling somewhat usable
        requiredArgs = inspect.getargspec(func)[0][1:]
        providedArgs = argv[2:]
        defaultArgs = inspect.getargspec(func)[3] or ()
        if len(providedArgs) + len(defaultArgs) < len(requiredArgs):
            print "%s takes %d arguments:" % (cmd,len(requiredArgs))
            self.__printArguments(func)
            return
        else:
            neededDefaultArgs = len(requiredArgs) - len(providedArgs)
            if neededDefaultArgs == 0:
                combinedArgs = tuple(providedArgs)
            else:
                combinedArgs = tuple(providedArgs) + defaultArgs[-(neededDefaultArgs):]
        func(*combinedArgs)

    def __printValidCommands(self):
        
        print "Valid commands are:", ", ".join(
            [str(m) for m in dir(self) if (m != "Dispatch" and
                                           not m.startswith("_") and
                                           callable(getattr(self, m)))]
            )
             
    def __printArguments(self,func):
        args = inspect.getargspec(func)[0][1:]
        defaultArgs = list(inspect.getargspec(func)[3] or ())
        # 'pad' defaultArgs so that it's the same len as args
        for i in range(len(args)-len(defaultArgs)):
            defaultArgs.insert(0,None)
            
        for i in range(len(args)):
            if not defaultArgs[i]:
                print "* %s" % args[i]
            else:
                print "* %s=%s" % (args[i], defaultArgs[i])
            
    
class Test:

    def foo(self):
        print "foo() called"

    def bar(self, someStr, someOtherString="blahonga"):
        print "bar(%s, %s) called" % (someStr, someOtherString)

    def baz(self, one, two, three, four="x", five="y", six="z"):
        print "baz(%s, %s, %s, %s, %s, %s) called" % (one,two,three,four,five,six)
    

if __name__ == "__main__":
    Test.__bases__ += (DispatchMixin,)
    t = Test()
    t.dispatch()
