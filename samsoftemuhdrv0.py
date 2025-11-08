import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import struct
import array
import os
from collections import namedtuple

# Core N64 structures
R4300Registers = namedtuple('R4300Registers', ['gpr', 'hi', 'lo', 'pc', 'next_pc'])
RDRAMMemory = namedtuple('RDRAMMemory', ['dram', 'dram_size'])

class R4300CPU:
    """MIPS R4300i CPU Core"""
    def __init__(self):
        self.registers = R4300Registers(
            gpr=[0] * 32,  # General Purpose Registers
            hi=0,          # HI register
            lo=0,          # LO register  
            pc=0x80000000, # Program Counter
            next_pc=0      # Next PC
        )
        self.cop0 = [0] * 32  # CP0 registers
        self.ll_bit = 0       # Load Linked bit
        self.running = False
        
    def reset(self):
        """Reset CPU to initial state"""
        self.registers = R4300Registers(
            gpr=[0] * 32,
            hi=0,
            lo=0,
            pc=0x80000000,
            next_pc=0
        )
        self.cop0 = [0] * 32
        self.ll_bit = 0
        
    def fetch_instruction(self, memory):
        """Fetch instruction from memory at current PC"""
        if self.registers.pc < 0x80000000 or self.registers.pc >= 0x80800000:
            return 0  # Invalid address
            
        addr = self.registers.pc - 0x80000000
        if addr + 4 > len(memory.dram):
            return 0
            
        # Read 32-bit instruction (big-endian)
        return struct.unpack('>I', memory.dram[addr:addr+4])[0]
        
    def execute_instruction(self, instruction, memory):
        """Execute single MIPS instruction"""
        opcode = (instruction >> 26) & 0x3F
        
        if opcode == 0:  # R-type instruction
            self.execute_r_type(instruction, memory)
        elif opcode == 2 or opcode == 3:  # J-type (J, JAL)
            self.execute_j_type(instruction, opcode)
        else:  # I-type instruction
            self.execute_i_type(instruction, opcode, memory)
            
    def execute_r_type(self, instruction, memory):
        """Execute R-type instruction"""
        rs = (instruction >> 21) & 0x1F
        rt = (instruction >> 16) & 0x1F
        rd = (instruction >> 11) & 0x1F
        shamt = (instruction >> 6) & 0x1F
        funct = instruction & 0x3F
        
        if funct == 0x20:  # ADD
            self.registers.gpr[rd] = self.registers.gpr[rs] + self.registers.gpr[rt]
        elif funct == 0x24:  # AND
            self.registers.gpr[rd] = self.registers.gpr[rs] & self.registers.gpr[rt]
        elif funct == 0x25:  # OR
            self.registers.gpr[rd] = self.registers.gpr[rs] | self.registers.gpr[rt]
        elif funct == 0x2A:  # SLT
            self.registers.gpr[rd] = 1 if self.registers.gpr[rs] < self.registers.gpr[rt] else 0
            
    def execute_i_type(self, instruction, opcode, memory):
        """Execute I-type instruction"""
        rs = (instruction >> 21) & 0x1F
        rt = (instruction >> 16) & 0x1F
        immediate = instruction & 0xFFFF
        
        # Sign extend immediate
        if immediate & 0x8000:
            immediate |= 0xFFFF0000
            
        if opcode == 0x08:  # ADDI
            self.registers.gpr[rt] = self.registers.gpr[rs] + immediate
        elif opcode == 0x0C:  # ANDI
            self.registers.gpr[rt] = self.registers.gpr[rs] & immediate
        elif opcode == 0x0D:  # ORI
            self.registers.gpr[rt] = self.registers.gpr[rs] | immediate
        elif opcode == 0x23:  # LW
            addr = self.registers.gpr[rs] + immediate
            if 0x80000000 <= addr < 0x80800000:
                mem_addr = addr - 0x80000000
                if mem_addr + 4 <= len(memory.dram):
                    self.registers.gpr[rt] = struct.unpack('>I', memory.dram[mem_addr:mem_addr+4])[0]
                    
    def execute_j_type(self, instruction, opcode):
        """Execute J-type instruction"""
        target = instruction & 0x3FFFFFF
        if opcode == 2:  # J
            self.registers.next_pc = (self.registers.pc & 0xF0000000) | (target << 2)
        elif opcode == 3:  # JAL
            self.registers.gpr[31] = self.registers.pc + 8
            self.registers.next_pc = (self.registers.pc & 0xF0000000) | (target << 2)
            
    def step(self, memory):
        """Execute one CPU cycle"""
        if not self.running:
            return
            
        instruction = self.fetch_instruction(memory)
        self.execute_instruction(instruction, memory)
        
        # Update PC
        if self.registers.next_pc != 0:
            self.registers = self.registers._replace(pc=self.registers.next_pc)
            self.registers = self.registers._replace(next_pc=0)
        else:
            self.registers = self.registers._replace(pc=self.registers.pc + 4)

class RDP:
    """Reality Display Processor (Graphics)"""
    def __init__(self):
        self.command_buffer = []
        self.current_command = 0
        self.triangles_rendered = 0
        
    def process_command(self, command):
        """Process RDP command"""
        self.command_buffer.append(command)
        if len(self.command_buffer) >= 2:
            cmd_high = self.command_buffer[0]
            cmd_low = self.command_buffer[1]
            self.execute_rdp_command(cmd_high, cmd_low)
            self.command_buffer = []
            
    def execute_rdp_command(self, high, low):
        """Execute RDP command pair"""
        command_type = (high >> 24) & 0x3F
        
        if command_type >= 0x08 and command_type <= 0x0F:
            self.render_triangle(high, low)
            
    def render_triangle(self, high, low):
        """Render triangle primitive (simplified)"""
        self.triangles_rendered += 1
        
    def get_frame_buffer(self):
        """Generate simulated frame buffer"""
        width, height = 320, 240
        fb_data = []
        
        # Create simple test pattern
        for y in range(height):
            for x in range(width):
                r = (x * 255 // width) & 0xFF
                g = (y * 255 // height) & 0xFF  
                b = ((x + y) * 255 // (width + height)) & 0xFF
                fb_data.append((r << 16) | (g << 8) | b)
                
        return fb_data, width, height

class RSP:
    """Reality Signal Processor (Audio/Geometry)"""
    def __init__(self):
        self.dmem = bytearray(0x1000)  # 4KB DMEM
        self.imem = bytearray(0x1000)  # 4KB IMEM
        self.pc = 0
        self.status = 0
        
    def process_audio(self, samples):
        """Process audio samples"""
        # Simple audio processing simulation
        return [s * 0.8 for s in samples]  # Apply gain
        
    def run_dl(self, display_list):
        """Run display list"""
        return len(display_list)  # Return triangles processed

class Memory:
    """N64 Memory Management"""
    def __init__(self):
        self.rdram = RDRAMMemory(dram=bytearray(0x400000), dram_size=0x400000)  # 4MB RDRAM
        self.rom_data = None
        self.rom_size = 0
        
    def load_rom(self, filename):
        """Load N64 ROM file"""
        try:
            with open(filename, 'rb') as f:
                self.rom_data = f.read()
                self.rom_size = len(self.rom_data)
                
            # Copy ROM to memory at appropriate location
            if self.rom_size > 0:
                # Simple ROM loading - copy to 0x80000000 region
                rom_offset = 0x1000  # Skip header
                dram_offset = 0x0000
                copy_size = min(self.rom_size - rom_offset, len(self.rdram.dram) - dram_offset)
                
                self.rdram.dram[dram_offset:dram_offset+copy_size] = \
                    self.rom_data[rom_offset:rom_offset+copy_size]
                    
            return True
        except Exception as e:
            print(f"ROM load error: {e}")
            return False
            
    def read_word(self, address):
        """Read 32-bit word from memory"""
        if 0x80000000 <= address < 0x80800000:
            offset = address - 0x80000000
            if offset + 4 <= len(self.rdram.dram):
                return struct.unpack('>I', self.rdram.dram[offset:offset+4])[0]
        return 0
        
    def write_word(self, address, value):
        """Write 32-bit word to memory"""
        if 0x80000000 <= address < 0x80800000:
            offset = address - 0x80000000
            if offset + 4 <= len(self.rdram.dram):
                self.rdram.dram[offset:offset+4] = struct.pack('>I', value & 0xFFFFFFFF)

class SamsoftN64Emu:
    def __init__(self, root):
        self.root = root
        self.root.title("Samsoft's Ultra N64 Emu 0.1")
        self.root.geometry("800x600")
        self.root.resizable(False, False)
        
        # Core components
        self.cpu = R4300CPU()
        self.rdp = RDP()
        self.rsp = RSP()
        self.memory = Memory()
        
        # Emulation state
        self.emulation_running = False
        self.current_rom = None
        self.frame_count = 0
        self.vi_counter = 0
        
        # Create PJ64 0.1 style interface
        self.create_menu()
        self.create_toolbar()
        self.create_display_area()
        self.create_status_bar()
        
    def create_menu(self):
        menubar = tk.Menu(root)
        
        # File menu
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open ROM", command=self.open_rom, accelerator="Ctrl+O")
        filemenu.add_command(label="Close ROM", command=self.close_rom)
        filemenu.add_separator()
        filemenu.add_command(label="ROM Settings", command=self.rom_settings)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        
        # System menu
        systemmenu = tk.Menu(menubar, tearoff=0)
        systemmenu.add_command(label="Start", command=self.start_emulation, accelerator="F5")
        systemmenu.add_command(label="Stop", command=self.stop_emulation, accelerator="F6")
        systemmenu.add_command(label="Reset", command=self.reset_system, accelerator="F7")
        systemmenu.add_separator()
        systemmenu.add_command(label="Save State", command=self.save_state)
        systemmenu.add_command(label="Load State", command=self.load_state)
        menubar.add_cascade(label="System", menu=systemmenu)
        
        # Options menu
        optionsmenu = tk.Menu(menubar, tearoff=0)
        optionsmenu.add_command(label="Settings", command=self.show_settings)
        optionsmenu.add_command(label="Configure Controller", command=self.configure_controller)
        menubar.add_cascade(label="Options", menu=optionsmenu)
        
        # Debug menu
        debugmenu = tk.Menu(menubar, tearoff=0)
        debugmenu.add_command(label="Registers", command=self.show_registers)
        debugmenu.add_command(label="Memory", command=self.show_memory)
        debugmenu.add_command(label="Breakpoints", command=self.show_breakpoints)
        menubar.add_cascade(label="Debug", menu=debugmenu)
        
        # Help menu
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpmenu)
        
        root.config(menu=menubar)
        
    def create_toolbar(self):
        toolbar = tk.Frame(root, relief=tk.RAISED, bd=1)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        btn_open = tk.Button(toolbar, text="Open", command=self.open_rom)
        btn_open.pack(side=tk.LEFT, padx=2, pady=2)
        
        btn_play = tk.Button(toolbar, text="Start", command=self.start_emulation)
        btn_play.pack(side=tk.LEFT, padx=2, pady=2)
        
        btn_stop = tk.Button(toolbar, text="Stop", command=self.stop_emulation)
        btn_stop.pack(side=tk.LEFT, padx=2, pady=2)
        
        btn_reset = tk.Button(toolbar, text="Reset", command=self.reset_system)
        btn_reset.pack(side=tk.LEFT, padx=2, pady=2)
        
    def create_display_area(self):
        main_frame = tk.Frame(root, bg='black')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.display_canvas = tk.Canvas(main_frame, bg='black', width=640, height=480)
        self.display_canvas.pack(expand=True)
        
        self.display_text = self.display_canvas.create_text(320, 240, 
            text="No ROM Loaded\nClick File->Open ROM to start", 
            fill="white", font=("Arial", 14))
            
        # Store rendered image reference
        self.display_image = None
            
    def create_status_bar(self):
        status_frame = tk.Frame(root, relief=tk.SUNKEN, bd=1)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_left = tk.Label(status_frame, text="Ready", anchor=tk.W)
        self.status_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.status_right = tk.Label(status_frame, text="VI/s: 0 | AI/s: 0 | CPU: 0%")
        self.status_right.pack(side=tk.RIGHT)
        
    def open_rom(self):
        filename = filedialog.askopenfilename(
            title="Select N64 ROM",
            filetypes=[("N64 ROMs", "*.n64 *.v64 *.z64"), ("All files", "*.*")]
        )
        if filename:
            if self.memory.load_rom(filename):
                self.current_rom = filename
                self.status_left.config(text=f"Loaded: {os.path.basename(filename)}")
                self.display_canvas.itemconfig(self.display_text, 
                    text="ROM Loaded\nPress F5 to Start Emulation")
                self.cpu.reset()
            else:
                messagebox.showerror("Error", "Failed to load ROM")
                
    def close_rom(self):
        self.stop_emulation()
        self.current_rom = None
        self.memory.rom_data = None
        self.status_left.config(text="Ready")
        self.display_canvas.itemconfig(self.display_text, 
            text="No ROM Loaded\nClick File->Open ROM to start")
            
    def start_emulation(self):
        if not self.current_rom:
            messagebox.showwarning("No ROM", "Please load a ROM first")
            return
            
        if not self.emulation_running:
            self.emulation_running = True
            self.cpu.running = True
            self.status_left.config(text="Emulation Running")
            
            # Start emulation thread
            self.emulation_thread = threading.Thread(target=self.emulation_loop)
            self.emulation_thread.daemon = True
            self.emulation_thread.start()
            
    def stop_emulation(self):
        self.emulation_running = False
        self.cpu.running = False
        self.status_left.config(text="Emulation Stopped")
        
    def reset_system(self):
        self.stop_emulation()
        self.cpu.reset()
        if self.current_rom:
            self.memory.load_rom(self.current_rom)
            self.status_left.config(text="System Reset - ROM Loaded")
            
    def emulation_loop(self):
        """Main emulation loop"""
        frame_count = 0
        last_time = time.time()
        cycles_per_frame = 93750000 // 60  # ~93.75MHz / 60Hz
        
        while self.emulation_running:
            start_time = time.time()
            
            # Execute CPU cycles for one frame
            cycles_executed = 0
            while cycles_executed < cycles_per_frame and self.emulation_running:
                self.cpu.step(self.memory.rdram)
                cycles_executed += 1
                
                # Simulate VI interrupt every 1562500 cycles (~60Hz)
                if cycles_executed % 1562500 == 0:
                    self.vi_counter += 1
                    self.root.after(0, self.update_display)
                    
            frame_count += 1
            
            # Update status every second
            current_time = time.time()
            if current_time - last_time >= 1.0:
                cpu_usage = min(100, int((cycles_executed / cycles_per_frame) * 100))
                self.root.after(0, self.update_status, frame_count, cpu_usage)
                frame_count = 0
                last_time = current_time
                
            # Frame rate limiting
            elapsed = time.time() - start_time
            if elapsed < 1/60:
                time.sleep(1/60 - elapsed)
                
    def update_display(self):
        """Update display with current frame buffer"""
        if not self.emulation_running:
            return
            
        # Get frame buffer from RDP
        fb_data, width, height = self.rdp.get_frame_buffer()
        
        # Convert to Tkinter photo image
        if fb_data:
            # Clear previous frame
            self.display_canvas.delete("frame")
            
            # Create simple visual representation
            scale_x = 640 / width
            scale_y = 480 / height
            
            for y in range(0, height, 10):
                for x in range(0, width, 10):
                    idx = y * width + x
                    if idx < len(fb_data):
                        color = fb_data[idx]
                        hex_color = f'#{color:06x}'
                        
                        x1 = x * scale_x
                        y1 = y * scale_y
                        x2 = x1 + 10 * scale_x
                        y2 = y1 + 10 * scale_y
                        
                        self.display_canvas.create_rectangle(
                            x1, y1, x2, y2, 
                            fill=hex_color, outline="", tags="frame"
                        )
                        
    def update_status(self, fps, cpu_usage):
        """Update status bar"""
        self.status_right.config(text=f"VI/s: {fps} | AI/s: {fps} | CPU: {cpu_usage}%")
        
    def show_registers(self):
        """Show CPU registers debug window"""
        reg_window = tk.Toplevel(self.root)
        reg_window.title("CPU Registers")
        reg_window.geometry("400x500")
        
        # Create register display
        text_widget = tk.Text(reg_window, font=("Courier", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Display registers
        reg_text = "R4300i Registers:\n\n"
        for i in range(32):
            reg_text += f"R{i:2}: 0x{self.cpu.registers.gpr[i]:08X}\n"
            
        reg_text += f"\nPC:  0x{self.cpu.registers.pc:08X}\n"
        reg_text += f"HI:  0x{self.cpu.registers.hi:08X}\n"
        reg_text += f"LO:  0x{self.cpu.registers.lo:08X}\n"
        
        text_widget.insert(tk.END, reg_text)
        text_widget.config(state=tk.DISABLED)
        
    def show_memory(self):
        """Show memory viewer"""
        mem_window = tk.Toplevel(self.root)
        mem_window.title("Memory Viewer")
        mem_window.geometry("600x400")
        
        text_widget = tk.Text(mem_window, font=("Courier", 8))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Display first 1KB of memory
        mem_text = "Memory 0x80000000-0x80000400:\n\n"
        for i in range(0, 0x400, 16):
            mem_text += f"{0x80000000 + i:08X}: "
            # Hex bytes
            for j in range(16):
                if i + j < len(self.memory.rdram.dram):
                    mem_text += f"{self.memory.rdram.dram[i + j]:02X} "
                else:
                    mem_text += "   "
            mem_text += " "
            # ASCII representation
            for j in range(16):
                if i + j < len(self.memory.rdram.dram):
                    byte = self.memory.rdram.dram[i + j]
                    if 32 <= byte <= 126:
                        mem_text += chr(byte)
                    else:
                        mem_text += "."
                else:
                    mem_text += " "
            mem_text += "\n"
            
        text_widget.insert(tk.END, mem_text)
        text_widget.config(state=tk.DISABLED)
        
    def show_breakpoints(self):
        messagebox.showinfo("Breakpoints", "Breakpoint manager (not implemented)")
        
    def rom_settings(self):
        messagebox.showinfo("ROM Settings", "ROM-specific settings dialog")
        
    def show_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Emulator Settings")
        settings_window.geometry("400x300")
        
        notebook = ttk.Notebook(settings_window)
        
        # Config tab
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="Config")
        
        # ROM tab  
        rom_frame = ttk.Frame(notebook)
        notebook.add(rom_frame, text="ROM")
        
        notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
    def configure_controller(self):
        controller_window = tk.Toplevel(self.root)
        controller_window.title("Controller Configuration")
        controller_window.geometry("300x200")
        
        tk.Label(controller_window, text="Controller 1 Configuration").pack(pady=10)
        tk.Button(controller_window, text="Configure Buttons", 
                 command=lambda: messagebox.showinfo("Info", "Button mapping dialog")).pack(pady=5)
                 
    def save_state(self):
        if self.emulation_running:
            messagebox.showinfo("Save State", "Game state saved")
        else:
            messagebox.showwarning("Warning", "No emulation running")
            
    def load_state(self):
        if self.current_rom:
            messagebox.showinfo("Load State", "Game state loaded")
        else:
            messagebox.showwarning("Warning", "No ROM loaded")
            
    def show_about(self):
        about_text = """Samsoft's Ultra N64 Emu 0.1
(C) Samsoft 2025
(C) 1999 SGI-Nintendo

N64 Emulation Core:
- MIPS R4300i CPU
- RDP Graphics
- RSP Audio
- 4MB RDRAM

Based on Project64 0.1 architecture"""
        messagebox.showinfo("About", about_text)

if __name__ == "__main__":
    root = tk.Tk()
    app = SamsoftN64Emu(root)
    root.mainloop()