from tkinter import Tk, Button, Frame, Entry, END
import tkinter.messagebox
import csv, datetime, webbrowser
from pathlib import Path
import clipboard

w = 800
h = 750


# Commands 
def openDocs():
    webbrowser.open(str(Path.home() / 'Documents' / 'Projects' / 'Python-KB'))
def openCustDocs():
    webbrowser.open(str(Path.home() / 'Documents'))    
def openPrinterIP():
    webbrowser.open(str(Path.home() / 'Downloads'))    
def alerts():
    webbrowser.open('Notifications.csv') 
def sendEmail():
    webbrowser.open('C:/sendEmail/')  
def o365():
    webbrowser.open('O365.csv')  
def fire():
    webbrowser.open('Firewall.csv')     
def creds():
    webbrowser.open('Credentials.csv') 
def kb():
    #webbrowser.open('http://google.com')
    webbrowser.open('KB.csv')     


class Homework(Frame):
    def __init__(self, parent=None):
        # Initial Config
        Frame.__init__(self,parent)
        self.parent = parent
        self.pack()
        self.fill_screen()
        # Positioning Default Window Position Upon Execution
        ws = root.winfo_screenwidth()
        hs = root.winfo_screenheight()
        x = (ws) - (w + 20)    
        y = (hs) - (h + 83)
        root.geometry('%dx%d+%d+%d' % (w, h, x, y))
        # Defines Title Of Tkinter Window Instance
        title = str(datetime.date.today())
        self.winfo_toplevel().title(title)

   
    
    def display(self):
        r = 0
        with open("Notifications.csv", newline = "") as file:
            reader = csv.reader(file)
            for col in reader:
                c = 0
                for row in col:
                    if (r == 9): 
                        label = tkinter.Label(self.final_frame, width = 30, height = 1, \
                                         text = "- " + row, bg='white', relief = tkinter.RIDGE)
                        label.grid(row = r, column = c)
                        c += 1
                    elif (r == 8):
                        label = tkinter.Label(self.final_frame, width = 30, height = 1, \
                                         text = "---------------------" + row, bg='white', relief = tkinter.RIDGE)
                        label.grid(row = r, column = c)
                        c += 1 
                    elif (r == 7):
                        label = tkinter.Label(self.final_frame, width = 30, height = 1, \
                                         text = row, fg='white', bg='black', relief = tkinter.RIDGE)
                        label.grid(row = r, column = c)
                        c += 1
                    elif (r == 1):
                        label = tkinter.Label(self.final_frame, width = 30, height = 1, \
                                         text = "---------------------" + row, bg='white', relief = tkinter.RIDGE)
                        label.grid(row = r, column = c)
                        c += 1 
                    elif (r > 1): 
                        label = tkinter.Label(self.final_frame, width = 30, height = 3, \
                                         text = "- " + row, fg='black',  bg='white',relief = tkinter.RIDGE)
                        label.grid(row = r, column = c)
                        c += 1
                    else:
                        label = tkinter.Label(self.final_frame, width = 30, height = 4, \
                                         text = row, fg='white', bg='black', relief = tkinter.RIDGE)
                        label.grid(row = r, column = c)
                        c += 1
                r += 1

    def fill_screen(self):

        # 4 Frames/Containers of the window
        self.top_frame = tkinter.Frame()
        self.info1_frame = tkinter.Frame()  
        self.info2_frame = tkinter.Frame() 
        self.info3_frame = tkinter.Frame()    
        self.space_frame = tkinter.Frame()          
        self.mid_frame = tkinter.Frame()
        self.bottom_frame = tkinter.Frame()
        self.final_frame = tkinter.Frame()

        # Creates the top frame widgets
        self.spacing_label = tkinter.Label(self.top_frame, \
                                 text="\n")
        self.value = tkinter.StringVar()



        self.popup1 = tkinter.Button(self.info1_frame, \
                                        text=' Email Hosting ', \
                                        command=o365)
        self.popup2 = tkinter.Button(self.info1_frame, \
                                          text=' Send Email ', \
                                          command=sendEmail)
        self.popup3 = tkinter.Button(self.info1_frame, \
                                          text=' Firewall Admin ', \
                                          command=fire)
        self.popup4 = tkinter.Button(self.info1_frame, \
                                          text=' Server/Local Creds ', \
                                          command=creds)
        self.popup5 = tkinter.Button(self.info1_frame, \
                                          text=' Knowledge Base ', \
                                          command=kb)


        self.popup6 = tkinter.Button(self.info2_frame, \
                                        text=' Customer Docs ', \
                                        command=openCustDocs)
        self.popup7 = tkinter.Button(self.info2_frame, \
                                          text=' Printer IPs ', \
                                          command=openPrinterIP)
        self.popup8 = tkinter.Button(self.info2_frame, \
                                          text=' IWSIT Docs ', \
                                          command=root.destroy)
        self.popup9 = tkinter.Button(self.info2_frame, \
                                          text=' T3 Exchange ', \
                                          command=root.destroy)
        self.popup10 = tkinter.Button(self.info2_frame, \
                                          text=' SC Docs ', \
                                          command=root.destroy)

        self.popup11 = tkinter.Button(self.info3_frame, \
                                          text='\n    IT Glue    \n', \
                                          command=root.destroy)
        self.popup12 = tkinter.Button(self.info3_frame, \
                                          text='\n    Cloud    \n', \
                                          command=root.destroy)
        self.popup13 = tkinter.Button(self.info3_frame, \
                                          text='\n    Labtech    \n', \
                                          command=root.destroy)
        self.popup14 = tkinter.Button(self.info3_frame, \
                                          text='\n    Webmail    \n', \
                                          command=root.destroy)



        self.spacing_label2 = tkinter.Label(self.space_frame, \
                                 text="\n")


        self.liveType_label = tkinter.Label(self.mid_frame, \
                                    textvariable="self.value")

        # Creates the mid frame widgets
        #self.assignment_label = tkinter.Label(self.mid_frame, \
        #            text='Add New Assignment: ')
        #self.user_input = tkinter.Entry(self.mid_frame, \
        #                                width=25)

        self.doc_button = tkinter.Button(self.mid_frame, \
                                        text='Open Web Browser', \
                                        command=openDocs)
        self.spacing2_label = tkinter.Label(self.mid_frame, \
                                 text="")

        # Creates the bottom frame widgets (View logs or quit)
        self.save_button = tkinter.Button(self.bottom_frame, \
                                        text='Edit', \
                                        command=alerts)
        self.quit_button = tkinter.Button(self.bottom_frame, \
                                          text='Quit', \
                                          command=root.destroy)
        self.spacing3_label = tkinter.Label(self.bottom_frame, \
                                 text="")

        # Creates the bottom frame widgets (View logs or quit)
        

        # Creates final frame widget - opens and displays Notifications.csv
        self.display()

        # Packing widgets,buttons,and frames
        self.spacing_label.pack(side='left')
        self.liveType_label.pack()
        self.doc_button.pack()
        self.spacing2_label.pack(side='left')
        #self.assignment_label.pack(side='left')
        #self.user_input.pack(side='right')
        self.save_button.pack(side='left')
        self.quit_button.pack(side='right')
        self.spacing3_label.pack()
        self.popup1.pack(side='left')
        self.popup2.pack(side='left')
        self.popup3.pack(side='left')
        self.popup4.pack(side='left')
        self.popup5.pack(side='left')
        self.popup6.pack(side='left')
        self.popup7.pack(side='left')
        self.popup8.pack(side='left')
        self.popup9.pack(side='left')
        self.popup10.pack(side='left')
        self.popup11.pack(side='left')
        self.popup12.pack(side='left')
        self.popup13.pack(side='left')
        self.popup14.pack(side='left')
        self.spacing_label2.pack(side='left')
        self.top_frame.pack()
        self.info1_frame.pack()
        self.info2_frame.pack()
        self.info3_frame.pack()
        self.space_frame.pack()
        self.final_frame.pack()
        self.mid_frame.pack()
        self.bottom_frame.pack()



#############
# Statements  #
#############

root = Tk()
hw = Homework(root)
root.mainloop()

# clipboard.clippy("This is just a tester")
# ^ Keeping that for debugging..
quit()
