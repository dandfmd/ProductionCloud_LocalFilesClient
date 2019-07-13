from tkinter import *
import asyncio
async def ask_login():
    user=password=None

     

    def ask():
        main = Tk()
        main.title('Inicia sesión')
        main.geometry('225x150')
        try: #Marcaba error en una compu del taller
            main.eval('tk::PlaceWindow %s center' % main.winfo_pathname(main.winfo_id()))
        except:
            pass
        def login(*event):
            nonlocal user
            nonlocal password   
            # Able to be called from a key binding or a button click because of the '*event'
            user= username_box.get()
            password= password_box.get()
            main.destroy()
            # If I wanted I could also pass the username and password I got above to another 
            # function from here.
        def clear_widget(event):
         
            # will clear out any entry boxes defined below when the user shifts
            # focus to the widgets defined below
            if username_box == main.focus_get() and username_box.get() == 'Usuario':
                username_box.delete(0, END)
            elif password_box == password_box.focus_get() and password_box.get() == '     ':
                password_box.delete(0, END)
         
        def repopulate_defaults(event):
         
            # will repopulate the default text previously inside the entry boxes defined below if
            # the user does not put anything in while focused and changes focus to another widget
            if username_box != main.focus_get() and username_box.get() == '':
                username_box.insert(0, 'Enter Username')
            elif password_box != main.focus_get() and password_box.get() == '':
                password_box.insert(0, '     ')
        # defines a grid 50 x 50 cells in the main window
        rows = 0
        while rows < 10:
            main.rowconfigure(rows, weight=1)
            main.columnconfigure(rows, weight=1)
            rows += 1
         
         
        # adds username entry widget and defines its properties
        username_box = Entry(main)
        username_box.insert(0, 'Usuario')
        username_box.bind("<FocusIn>", clear_widget)
        username_box.bind('<FocusOut>', repopulate_defaults)
        username_box.grid(row=1, column=5, sticky='NS')
         
         
        # adds password entry widget and defines its properties
        password_box = Entry(main, show='*')
        password_box.insert(0, '     ')
        password_box.bind("<FocusIn>", clear_widget)
        password_box.bind('<FocusOut>', repopulate_defaults)
        password_box.bind('<Return>', login)
        password_box.grid(row=2, column=5, sticky='NS')
         
         
        # adds login button and defines its properties
        login_btn = Button(main, text='Iniciar sesión', command=login)
        login_btn.bind('<Return>', login)
        login_btn.grid(row=5, column=5, sticky='NESW')
         
         
        main.mainloop()
    
    await asyncio.get_event_loop().run_in_executor(None, ask)
    return user,password
    
 

