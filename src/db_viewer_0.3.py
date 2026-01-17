import sys
import sqlite3
import csv
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QComboBox, QTableView, QFileDialog,
                            QPushButton, QMessageBox, QTextEdit, QStatusBar,
                            QToolBar, QInputDialog, QSplitter, QListWidget,
                            QDialog, QFormLayout, QLineEdit, QDialogButtonBox)
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel, QSqlQuery
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QUndoStack, QUndoCommand

class AddRowDialog(QDialog):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Row")
        self.model = model
        self.layout = QFormLayout()
        
        self.inputs = []
        for col in range(model.columnCount()):
            header = model.headerData(col, Qt.Orientation.Horizontal)
            input_field = QLineEdit()
            self.inputs.append((header, input_field))
            self.layout.addRow(header, input_field)
        
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addRow(self.buttons)
        self.setLayout(self.layout)

    def get_values(self):
        return {header: input_field.text() for header, input_field in self.inputs}

class DatabaseViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Professional SQLite3 Database Viewer")
        self.resize(1000, 700)
        
        # Initialize undo stack
        self.undo_stack = QUndoStack(self)
        
        # Initialize status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("No database connected")
        
        # Initialize toolbar
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        
        # Toolbar actions
        self.open_db_action = QAction("Open DB", self)
        self.open_db_action.triggered.connect(self.open_database)
        self.new_table_action = QAction("New Table", self)
        self.new_table_action.triggered.connect(self.create_table)
        self.delete_table_action = QAction("Delete Table", self)
        self.delete_table_action.triggered.connect(self.delete_table)
        self.export_csv_action = QAction("Export to CSV", self)
        self.export_csv_action.triggered.connect(self.export_to_csv)
        self.add_row_action = QAction("Add Row", self)
        self.add_row_action.triggered.connect(self.add_row)
        self.add_column_action = QAction("Add Column", self)
        self.add_column_action.triggered.connect(self.add_column)
        self.delete_column_action = QAction("Delete Column", self)
        self.delete_column_action.triggered.connect(self.delete_column)
        self.undo_action = QAction("Undo", self)
        self.undo_action.triggered.connect(self.undo_stack.undo)
        self.undo_action.setEnabled(False)
        self.undo_stack.canUndoChanged.connect(self.undo_action.setEnabled)
        
        self.toolbar.addAction(self.open_db_action)
        self.toolbar.addAction(self.new_table_action)
        self.toolbar.addAction(self.delete_table_action)
        self.toolbar.addAction(self.add_row_action)
        self.toolbar.addAction(self.add_column_action)
        self.toolbar.addAction(self.delete_column_action)
        self.toolbar.addAction(self.export_csv_action)
        self.toolbar.addAction(self.undo_action)
        
        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Splitter for query and table view
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_layout.addWidget(self.splitter)
        
        # Query section
        self.query_widget = QWidget()
        self.query_layout = QVBoxLayout(self.query_widget)
        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText("Enter SQL query here...")
        self.execute_button = QPushButton("Execute Query")
        self.execute_button.clicked.connect(self.execute_query)
        self.query_history = QListWidget()
        self.query_history.itemDoubleClicked.connect(self.load_query_from_history)
        self.query_layout.addWidget(self.query_input)
        self.query_layout.addWidget(self.execute_button)
        self.query_layout.addWidget(self.query_history)
        
        # Table selection and view
        self.table_widget = QWidget()
        self.table_layout = QVBoxLayout(self.table_widget)
        self.table_combo = QComboBox()
        self.table_combo.currentTextChanged.connect(self.display_table)
        self.table_view = QTableView()
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_layout.addWidget(self.table_combo)
        self.table_layout.addWidget(self.table_view)
        
        self.splitter.addWidget(self.query_widget)
        self.splitter.addWidget(self.table_widget)
        self.splitter.setSizes([200, 400])
        
        self.db = None
        self.model = None
        self.connection_name = f"db_{id(self)}"

    def open_database(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open SQLite Database",
            "",
            "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        
        if file_name:
            try:
                # Close existing database if open
                if self.db and self.db.isOpen():
                    self.db.close()
                    QSqlDatabase.removeDatabase(self.connection_name)
                
                # Open new database
                self.db = QSqlDatabase.addDatabase("QSQLITE", self.connection_name)
                self.db.setDatabaseName(file_name)
                
                if not self.db.open():
                    QMessageBox.critical(self, "Error", "Could not open database")
                    self.status_bar.showMessage("Database connection failed")
                    return
                
                # Update UI
                self.table_combo.clear()
                tables = self.db.tables()
                self.table_combo.addItems(tables)
                self.status_bar.showMessage(f"Connected to: {file_name}")
                self.undo_stack.clear()
                
                if tables:
                    self.display_table(tables[0])
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error opening database: {str(e)}")
                self.status_bar.showMessage("Database connection failed")

    def display_table(self, table_name):
        if not table_name or not self.db:
            return
            
        try:
            # Create and set up the model
            self.model = QSqlTableModel(self, self.db)
            self.model.setTable(table_name)
            self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
            self.model.dataChanged.connect(self.on_data_changed)
            self.model.select()
            
            # Set up the view
            self.table_view.setModel(self.model)
            self.table_view.resizeColumnsToContents()
            self.status_bar.showMessage(f"Displaying table: {table_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error displaying table: {str(e)}")
            self.status_bar.showMessage("Error displaying table")

    def on_data_changed(self, top_left, bottom_right):
        # Record changes for undo
        row = top_left.row()
        col = top_left.column()
        new_value = self.model.data(top_left)
        old_value = self.model.data(top_left, Qt.ItemDataRole.UserRole)
        
        class UpdateCommand(QUndoCommand):
            def __init__(self, model, row, col, old_value, new_value, parent=None):
                super().__init__(parent)
                self.model = model
                self.row = row
                self.col = col
                self.old_value = old_value
                self.new_value = new_value
                self.setText(f"Update cell at row {row}, column {col}")
            
            def redo(self):
                self.model.setData(self.model.index(self.row, self.col), self.new_value)
            
            def undo(self):
                self.model.setData(self.model.index(self.row, self.col), self.old_value)
        
        if old_value != new_value:
            self.undo_stack.push(UpdateCommand(self.model, row, col, old_value, new_value))
            self.status_bar.showMessage(f"Cell updated at row {row}, column {col}")

    def execute_query(self):
        if not self.db or not self.db.isOpen():
            QMessageBox.warning(self, "Warning", "No database connected")
            return
            
        query_text = self.query_input.toPlainText().strip()
        if not query_text:
            return
            
        try:
            query = QSqlQuery(self.db)
            if query.exec(query_text):
                # Add to history
                self.query_history.addItem(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {query_text[:50]}...")
                
                # If it's a SELECT query, display results
                if query_text.strip().upper().startswith('SELECT'):
                    self.model = QSqlTableModel(self, self.db)
                    self.model.setQuery(query)
                    self.table_view.setModel(self.model)
                    self.table_view.resizeColumnsToContents()
                    self.status_bar.showMessage("Query executed successfully")
                else:
                    self.db.commit()
                    # Refresh table list if structure changed
                    self.table_combo.clear()
                    self.table_combo.addItems(self.db.tables())
                    self.status_bar.showMessage("Query executed successfully")
            else:
                QMessageBox.critical(self, "Error", f"Query error: {query.lastError().text()}")
                self.status_bar.showMessage("Query execution failed")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Query error: {str(e)}")
            self.status_bar.showMessage("Query execution failed")

    def create_table(self):
        if not self.db or not self.db.isOpen():
            QMessageBox.warning(self, "Warning", "No database connected")
            return
            
        table_name, ok = QInputDialog.getText(self, "New Table", "Enter table name:")
        if ok and table_name:
            try:
                query = QSqlQuery(self.db)
                # Basic table creation with an ID column
                create_sql = f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT)"
                if query.exec(create_sql):
                    self.db.commit()
                    self.table_combo.clear()
                    self.table_combo.addItems(self.db.tables())
                    self.status_bar.showMessage(f"Table {table_name} created")
                else:
                    QMessageBox.critical(self, "Error", f"Error creating table: {query.lastError().text()}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error creating table: {str(e)}")

    def delete_table(self):
        if not self.db or not self.db.isOpen():
            QMessageBox.warning(self, "Warning", "No database connected")
            return
            
        table_name = self.table_combo.currentText()
        if not table_name:
            return
            
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to delete table {table_name}?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                query = QSqlQuery(self.db)
                if query.exec(f"DROP TABLE {table_name}"):
                    self.db.commit()
                    self.table_combo.clear()
                    self.table_combo.addItems(self.db.tables())
                    self.table_view.setModel(None)
                    self.status_bar.showMessage(f"Table {table_name} deleted")
                else:
                    QMessageBox.critical(self, "Error", f"Error deleting table: {query.lastError().text()}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error deleting table: {str(e)}")

    def add_row(self):
        if not self.model or not self.db or not self.db.isOpen():
            QMessageBox.warning(self, "Warning", "No table selected or no database connected")
            return
            
        dialog = AddRowDialog(self.model, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.get_values()
            try:
                row = self.model.rowCount()
                self.model.insertRows(row, 1)
                for col, header in enumerate(values):
                    self.model.setData(self.model.index(row, col), values[header])
                
                if self.model.submitAll():
                    self.db.commit()
                    self.status_bar.showMessage("Row added successfully")
                    self.undo_stack.push(AddRowCommand(self.model, row))
                else:
                    QMessageBox.critical(self, "Error", f"Error adding row: {self.model.lastError().text()}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error adding row: {str(e)}")

    def add_column(self):
        if not self.db or not self.db.isOpen() or not self.table_combo.currentText():
            QMessageBox.warning(self, "Warning", "No table selected or no database connected")
            return
            
        column_name, ok = QInputDialog.getText(self, "Add Column", "Enter column name:")
        if ok and column_name:
            try:
                query = QSqlQuery(self.db)
                table_name = self.table_combo.currentText()
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT"
                if query.exec(alter_sql):
                    self.db.commit()
                    self.display_table(table_name)
                    self.status_bar.showMessage(f"Column {column_name} added")
                    self.undo_stack.push(AddColumnCommand(self.db, table_name, column_name))
                else:
                    QMessageBox.critical(self, "Error", f"Error adding column: {query.lastError().text()}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error adding column: {str(e)}")

    def delete_column(self):
        if not self.db or not self.db.isOpen() or not self.table_combo.currentText():
            QMessageBox.warning(self, "Warning", "No table selected or no database connected")
            return
            
        table_name = self.table_combo.currentText()
        columns = [self.model.headerData(i, Qt.Orientation.Horizontal) 
                  for i in range(self.model.columnCount())]
        column_name, ok = QInputDialog.getItem(self, "Delete Column", 
                                             "Select column to delete:", columns, 0, False)
        if ok and column_name:
            reply = QMessageBox.question(self, "Confirm Delete", 
                                       f"Are you sure you want to delete column {column_name}?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    # SQLite doesn't support direct column deletion, so we need to recreate the table
                    query = QSqlQuery(self.db)
                    # Get current table structure
                    query.exec(f"PRAGMA table_info({table_name})")
                    columns_info = []
                    while query.next():
                        col_name = query.value("name")
                        if col_name != column_name:
                            columns_info.append((col_name, query.value("type")))
                    
                    # Create new table
                    temp_table = f"{table_name}_temp"
                    columns_def = ", ".join(f"{col[0]} {col[1]}" for col in columns_info)
                    query.exec(f"CREATE TABLE {temp_table} ({columns_def})")
                    
                    # Copy data
                    columns_list = ", ".join(col[0] for col in columns_info)
                    query.exec(f"INSERT INTO {temp_table} ({columns_list}) SELECT {columns_list} FROM {table_name}")
                    
                    # Drop old table and rename new one
                    query.exec(f"DROP TABLE {table_name}")
                    query.exec(f"ALTER TABLE {temp_table} RENAME TO {table_name}")
                    
                    self.db.commit()
                    self.display_table(table_name)
                    self.status_bar.showMessage(f"Column {column_name} deleted")
                    self.undo_stack.push(DeleteColumnCommand(self.db, table_name, column_name))
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error deleting column: {str(e)}")

    def export_to_csv(self):
        if not self.model:
            QMessageBox.warning(self, "Warning", "No table selected")
            return
            
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save as CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_name:
            try:
                with open(file_name, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    # Write headers
                    headers = [self.model.headerData(i, Qt.Orientation.Horizontal) 
                              for i in range(self.model.columnCount())]
                    writer.writerow(headers)
                    
                    # Write data
                    for row in range(self.model.rowCount()):
                        row_data = []
                        for col in range(self.model.columnCount()):
                            data = self.model.data(self.model.index(row, col))
                            row_data.append(str(data))
                        writer.writerow(row_data)
                    self.status_bar.showMessage(f"Exported to {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error exporting to CSV: {str(e)}")
                self.status_bar.showMessage("Export failed")

    def load_query_from_history(self, item):
        query_text = item.text().split(": ", 1)[1] + "..."
        self.query_input.setText(query_text.rstrip("..."))

    def closeEvent(self, event):
        # Clean up database connection
        if self.db and self.db.isOpen():
            self.db.close()
        QSqlDatabase.removeDatabase(self.connection_name)
        event.accept()

class AddRowCommand(QUndoCommand):
    def __init__(self, model, row, parent=None):
        super().__init__(parent)
        self.model = model
        self.row = row
        self.setText("Add row")
        
    def redo(self):
        self.model.insertRows(self.row, 1)
        self.model.submitAll()
        
    def undo(self):
        self.model.removeRows(self.row, 1)
        self.model.submitAll()

class AddColumnCommand(QUndoCommand):
    def __init__(self, db, table_name, column_name, parent=None):
        super().__init__(parent)
        self.db = db
        self.table_name = table_name
        self.column_name = column_name
        self.setText(f"Add column {column_name}")
        
    def redo(self):
        query = QSqlQuery(self.db)
        query.exec(f"ALTER TABLE {self.table_name} ADD COLUMN {self.column_name} TEXT")
        self.db.commit()
        
    def undo(self):
        # Note: This is simplified; actual column deletion is more complex
        query = QSqlQuery(self.db)
        query.exec(f"PRAGMA table_info({self.table_name})")
        columns_info = []
        while query.next():
            col_name = query.value("name")
            if col_name != self.column_name:
                columns_info.append((col_name, query.value("type")))
        
        temp_table = f"{self.table_name}_temp"
        columns_def = ", ".join(f"{col[0]} {col[1]}" for col in columns_info)
        columns_list = ", ".join(col[0] for col in columns_info)
        
        query.exec(f"CREATE TABLE {temp_table} ({columns_def})")
        query.exec(f"INSERT INTO {temp_table} ({columns_list}) SELECT {columns_list} FROM {self.table_name}")
        query.exec(f"DROP TABLE {self.table_name}")
        query.exec(f"ALTER TABLE {temp_table} RENAME TO {self.table_name}")
        self.db.commit()

class DeleteColumnCommand(QUndoCommand):
    def __init__(self, db, table_name, column_name, parent=None):
        super().__init__(parent)
        self.db = db
        self.table_name = table_name
        self.column_name = column_name
        self.setText(f"Delete column {column_name}")
        
    def redo(self):
        query = QSqlQuery(self.db)
        query.exec(f"PRAGMA table_info({self.table_name})")
        columns_info = []
        while query.next():
            col_name = query.value("name")
            if col_name != self.column_name:
                columns_info.append((col_name, query.value("type")))
        
        temp_table = f"{self.table_name}_temp"
        columns_def = ", ".join(f"{col[0]} {col[1]}" for col in columns_info)
        columns_list = ", ".join(col[0] for col in columns_info)
        
        query.exec(f"CREATE TABLE {temp_table} ({columns_def})")
        query.exec(f"INSERT INTO {temp_table} ({columns_list}) SELECT {columns_list} FROM {self.table_name}")
        query.exec(f"DROP TABLE {self.table_name}")
        query.exec(f"ALTER TABLE {temp_table} RENAME TO {self.table_name}")
        self.db.commit()
        
    def undo(self):
        query = QSqlQuery(self.db)
        query.exec(f"ALTER TABLE {self.table_name} ADD COLUMN {self.column_name} TEXT")
        self.db.commit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = DatabaseViewer()
    viewer.show()
    sys.exit(app.exec())