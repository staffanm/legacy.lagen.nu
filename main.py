import Robot
reload(Robot)

if __name__ == "__main__":
    Robot.Get("http://www.regeringen.se/", UseCache=True)
