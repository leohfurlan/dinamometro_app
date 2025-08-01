# -*- coding: utf-8 -*-

"""
Dinamometro GUI v6.2 - Versão Final com Timer de Ensaio

Software completo para leitura de dados de um dinamômetro via Modbus,
com calibração de sinal, gravação de dados e um cronômetro visual
para o tempo de ensaio.

Bibliotecas necessárias:
pip install pymodbus matplotlib pyserial
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
import serial.tools.list_ports
import time
import threading

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class DinamometroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dinamômetro Digital v6.2 (com Timer)")
        self.root.geometry("800x680") # Aumentei um pouco a altura

        self.client = None
        self.is_connected = False
        self.is_recording = False
        self.start_time = 0
        self.output_file = None
        self.time_data = []
        self.force_data = []

        self.capacidade_kgf = 100.0
        self.modbus_address = 0
        self.modbus_slave_id = 1
        
        self.timer_job = None ### NOVO: Variável para controlar o timer ###

        self.create_widgets()

    def convert_value_from_raw(self, raw_value):
        signed_value = raw_value
        if signed_value > 32767:
            signed_value -= 65536
        if raw_value == 65535:
             return 0.0
        fator_escala = self.capacidade_kgf / 32767.0
        return signed_value * fator_escala

    def update_port_list(self, event=None):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combobox['values'] = ports

    def create_widgets(self):
        main_frame=ttk.Frame(self.root);main_frame.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)
        graph_frame=ttk.LabelFrame(main_frame,text="Gráfico Força vs. Tempo");graph_frame.pack(fill=tk.BOTH,expand=True,pady=5)
        self.fig=Figure(figsize=(6,4),dpi=100);self.ax=self.fig.add_subplot(111);self.ax.set_title("Ensaio em Tempo Real");self.ax.set_xlabel("Tempo (s)");self.ax.set_ylabel("Força (kgf)");self.ax.grid(True);self.line,=self.ax.plot([],[],'r-',label='Força');self.ax.legend();self.fig.tight_layout();self.canvas=FigureCanvasTkAgg(self.fig,master=graph_frame);self.canvas.draw();self.canvas.get_tk_widget().pack(side=tk.TOP,fill=tk.BOTH,expand=True)
        
        bottom_frame=ttk.Frame(main_frame);bottom_frame.pack(fill=tk.X,expand=False,pady=(10,0))
        
        display_frame=ttk.LabelFrame(bottom_frame,text="Leitura em Tempo Real",padding=10);display_frame.pack(side=tk.LEFT,fill=tk.Y,padx=(0,10))
        self.force_label=ttk.Label(display_frame,text="--- kgf",font=("Helvetica",28,"bold"),foreground="blue",width=7,anchor='center');self.force_label.pack(pady=5,padx=10)
        
        ### NOVO: LABEL PARA O TIMER ###
        self.timer_label = ttk.Label(display_frame, text="Tempo: 00:00.0", font=("Helvetica", 14))
        self.timer_label.pack(pady=(0, 5))
        ### -------------------------- ###
        
        controls_frame=ttk.Frame(bottom_frame);controls_frame.pack(side=tk.LEFT,fill=tk.X,expand=True)
        connection_frame=ttk.LabelFrame(controls_frame,text="Configuração",padding=5);connection_frame.grid(row=0,column=0,padx=5,pady=5,sticky="ew")
        ttk.Label(connection_frame,text="Porta:").grid(row=0,column=0,sticky="w",padx=5);self.port_combobox=ttk.Combobox(connection_frame,width=12);self.port_combobox.set("COM6");self.port_combobox.grid(row=0,column=1,padx=5);self.port_combobox.bind("<Button-1>",self.update_port_list)
        ttk.Label(connection_frame,text="Baud:").grid(row=0,column=2,sticky="w",padx=5);self.baud_entry=ttk.Entry(connection_frame,width=8);self.baud_entry.insert(0,"9600");self.baud_entry.grid(row=0,column=3,padx=5)
        self.connect_button=ttk.Button(connection_frame,text="Conectar",command=self.toggle_connection,width=12);self.connect_button.grid(row=0,column=4,padx=10)
        record_frame=ttk.LabelFrame(controls_frame,text="Gravação",padding=5);record_frame.grid(row=1,column=0,padx=5,pady=5,sticky="ew")
        ttk.Label(record_frame,text="Arquivo:").grid(row=0,column=0,sticky="w",padx=5);self.filename_entry=ttk.Entry(record_frame,width=30);self.filename_entry.insert(0,"ensaio_final_01.txt");self.filename_entry.grid(row=0,column=1,padx=5,sticky="ew")
        self.record_button=ttk.Button(record_frame,text="Iniciar Gravação",command=self.toggle_recording,state="disabled",width=15);self.record_button.grid(row=0,column=2,padx=10)
        self.status_bar=ttk.Label(self.root,text="Status: Desconectado",relief=tk.SUNKEN,anchor="w");self.status_bar.pack(side="bottom",fill="x");self.update_port_list()

    def toggle_connection(self):
        # A lógica de conexão não muda
        if not self.is_connected:
            port = self.port_combobox.get()
            try:
                self.client = ModbusSerialClient(port=port, baudrate=9600, parity='N', stopbits=1, bytesize=8, timeout=1, framer="rtu")
                if not self.client.connect(): raise ModbusException(f"Falha ao conectar na porta {port}")
                self.is_connected = True; self.status_bar.config(text=f"Status: Conectado a {port} via Modbus"); self.connect_button.config(text="Desconectar"); self.record_button.config(state="normal")
                self.read_thread = threading.Thread(target=self.read_modbus_data, daemon=True); self.read_thread.start()
            except Exception as e:
                messagebox.showerror("Erro de Conexão", f"Não foi possível conectar.\nErro: {e}")
                if self.client: self.client.close()
        else:
            self.is_connected = False; time.sleep(0.1)
            if self.client: self.client.close()
            self.status_bar.config(text="Status: Desconectado"); self.connect_button.config(text="Conectar"); self.record_button.config(state="disabled"); self.force_label.config(text="--- kgf")

    def read_modbus_data(self):
        # A lógica de leitura não muda
        while self.is_connected:
            try:
                result = self.client.read_holding_registers(address=self.modbus_address, count=1, slave=self.modbus_slave_id)
                if not result.isError():
                    raw_value = result.registers[0]
                    self.root.after(0, self.update_gui, raw_value)
                else:
                    print(f"Erro Modbus ao ler registrador: {result}")
            except Exception as e:
                print(f"Erro na thread de leitura: {e}"); self.is_connected = False; break
            time.sleep(0.2)
    
    ### NOVO: FUNÇÃO PARA ATUALIZAR O CRONÔMETRO ###
    def update_timer(self):
        if self.is_recording:
            elapsed_time = time.time() - self.start_time
            
            # Formata o tempo para MM:SS.d
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            tenths = int((elapsed_time * 10) % 10)
            
            self.timer_label.config(text=f"Tempo: {minutes:02d}:{seconds:02d}.{tenths}")
            
            # Agenda a próxima atualização
            self.timer_job = self.root.after(100, self.update_timer)

    def update_gui(self, raw_value):
        # A lógica de atualização da força não muda
        kgf_value = self.convert_value_from_raw(raw_value)
        self.force_label.config(text=f"{kgf_value:.2f} kgf")
        if self.is_recording:
            elapsed_time = time.time() - self.start_time; self.time_data.append(elapsed_time); self.force_data.append(kgf_value)
            print(f"Gravando: Tempo={elapsed_time:.2f}s, Força={kgf_value:.2f} kgf (raw: {raw_value})")
            if self.output_file: self.output_file.write(f"{elapsed_time:.4f},{kgf_value:.4f}\n")
            self.line.set_data(self.time_data, self.force_data)
            self.ax.relim(); self.ax.autoscale_view(); self.canvas.draw()
            
    def toggle_recording(self):
        if not self.is_recording:
            filename=self.filename_entry.get()
            if not filename: messagebox.showerror("Erro","Por favor, insira um nome."); return
            try:
                self.time_data.clear(); self.force_data.clear(); self.line.set_data([],[]); self.canvas.draw()
                self.output_file=open(filename,"w"); self.output_file.write("Tempo (s),Forca (kgf)\n")
                self.is_recording=True; self.start_time=time.time()
                
                ### ALTERADO: INICIA O TIMER ###
                self.update_timer()
                
                self.status_bar.config(text=f"Status: Gravando em {filename}")
                self.record_button.config(text="Parar Gravação"); self.connect_button.config(state="disabled"); self.filename_entry.config(state="disabled")
            except IOError as e: messagebox.showerror("Erro de Arquivo",f"Não foi possível criar o arquivo.\nErro: {e}")
        else:
            self.is_recording=False
            
            ### ALTERADO: PARA O TIMER ###
            if self.timer_job:
                self.root.after_cancel(self.timer_job)
                self.timer_job = None
            
            if self.output_file: self.output_file.close(); self.output_file=None
            self.status_bar.config(text=f"Status: Conectado. Gravação finalizada em {self.filename_entry.get()}")
            self.record_button.config(text="Iniciar Gravação"); self.connect_button.config(state="normal"); self.filename_entry.config(state="normal")
            
    def on_closing(self):
        # A lógica de fechamento não muda
        if self.is_connected: self.is_connected = False; time.sleep(0.2)
        if self.client and self.client.is_socket_open(): self.client.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DinamometroApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()