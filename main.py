import Robot
reload(Robot)

Robot.Get("http://www.regeringen.se/", UseCache=True)
