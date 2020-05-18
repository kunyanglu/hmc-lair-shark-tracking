
class ObjectState:
    def __init__(self, x, y, z, theta, time_stamp):
        # initialize auv's data
        self.x = x
        self.y = y
        self.z = z
        self.theta = theta
        self.time_stamp = time_stamp 

    def __repr__(self):
        return "(" + self.x + ", "  + self.y + ", " + self.z  + ", " +\
            self.theta  + ", " +  self.time_stamp + ")"

    def __str__(self):
        return "(" + str(self.x) + ", "  + str(self.y) + ", " + str(self.z)  + ", " +\
            str(self.theta) + ", " +  str(self.time_stamp) + ")"