from dash import html
class CustomType:
    def __init__(self, verify, inputstructure, selectstructure=lambda x:None, displayMethod=lambda x:x):
        self.check = verify
        self.inputs = inputstructure
        self.structureValue = None
        self.select = selectstructure
        self.displayMethod = displayMethod

    def verify(self, property, input):
        return self.check(property, input)

    def inputstructure(self, id):
        if not self.structureValue:
            self.structure, self.structureValue = self.inputs(id)
            return self.structure
        return self.inputs(id)[0]

    def selectstructure(self, id):
        return self.select(id)

    def getStructureValue(self):
        return self.structureValue

