from flask import Flask, request, render_template, jsonify, send_file
import os
import tempfile
import openpyxl
import pydicom
from dicompylercore import dicomparser, dvhcalc, dvh
import numpy as np
import pandas as pd
from openpyxl.utils import get_column_letter
from werkzeug.utils import secure_filename
import sys

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'dcm'}

def calculate_dvh(rtdose_path, rtstruct_path):
    print(f"Starting DVH calculation with files: {rtdose_path}, {rtstruct_path}")
    sys.stdout.flush()
    
    try:
        # Parse DICOM files
        dp_struct = dicomparser.DicomParser(rtstruct_path)
        dp_dose = dicomparser.DicomParser(rtdose_path)
        
        # Get structure information
        structures = dp_struct.GetStructures()
        print(f"Found structures: {[(id, s.get('name', 'Unknown')) for id, s in structures.items()]}")
        sys.stdout.flush()
        
        dvh_data = {}
        
        # Calculate DVH for each structure
        for roi_id, structure in structures.items():
            try:
                print(f"\nProcessing structure: {structure['name']} (ID: {roi_id})")
                sys.stdout.flush()
                
                # Skip empty structures
                if structure['empty']:
                    print(f"Skipping empty structure: {structure['name']}")
                    continue
                
                try:
                    # Calculate DVH with interpolation for better accuracy
                    print(f"Calculating DVH for: {structure['name']}")
                    sys.stdout.flush()
                    
                    # Load DICOM files
                    rtstruct = pydicom.read_file(rtstruct_path)
                    rtdose = pydicom.read_file(rtdose_path)
                    
                    calculated_dvh = dvhcalc.get_dvh(rtstruct, 
                                                    rtdose,
                                                    roi_id,
                                                    calculate_full_volume=True,
                                                    use_structure_extents=True)
                    
                    if calculated_dvh is None:
                        print(f"DVH calculation failed for: {structure['name']}")
                        continue
                    
                    # Get DVH description
                    print(f"DVH calculated for: {structure['name']}")
                    print("DVH Description:")
                    print(calculated_dvh.describe())
                    sys.stdout.flush()
                    
                    # Convert to relative volume (%)
                    total_volume = calculated_dvh.volume
                    if total_volume > 0:
                        volumes = (calculated_dvh.counts / calculated_dvh.counts[0]) * 100
                    else:
                        print(f"Warning: Zero volume for {structure['name']}")
                        continue
                    
                    # Convert numpy arrays to lists for JSON serialization
                    color = structure.get('color', [255, 0, 0])
                    if isinstance(color, np.ndarray):
                        color = color.tolist()
                    
                    # Helper function to safely convert DVH values
                    def get_dvh_value(value):
                        try:
                            if hasattr(value, 'value'):  # DVHValue object
                                return float(value.value)
                            return float(value)
                        except:
                            return None
                    
                    dvh_data[structure['name']] = {
                        'doses': calculated_dvh.bins.tolist(),
                        'volumes': volumes.tolist(),
                        'color': color,
                        'volume': float(total_volume),
                        'min_dose': get_dvh_value(calculated_dvh.min),
                        'max_dose': get_dvh_value(calculated_dvh.max),
                        'mean_dose': get_dvh_value(calculated_dvh.mean),
                        # Add more DVH statistics
                        'D100': get_dvh_value(calculated_dvh.D100),
                        'D98': get_dvh_value(calculated_dvh.D98),
                        'D95': get_dvh_value(calculated_dvh.D95),
                        'D2cc': get_dvh_value(calculated_dvh.D2cc)
                    }
                    print(f"Successfully added DVH data for: {structure['name']}")
                    print(f"Volume: {total_volume:.2f} cm³")
                    print(f"Min Dose: {get_dvh_value(calculated_dvh.min):.2f} Gy")
                    print(f"Max Dose: {get_dvh_value(calculated_dvh.max):.2f} Gy")
                    print(f"Mean Dose: {get_dvh_value(calculated_dvh.mean):.2f} Gy")
                    sys.stdout.flush()
                    
                except Exception as calc_error:
                    print(f"Error in DVH calculation for {structure['name']}: {str(calc_error)}")
                    import traceback
                    print(traceback.format_exc())
                    sys.stdout.flush()
                    continue
                
            except Exception as struct_error:
                print(f"Error processing structure {structure['name']}: {str(struct_error)}")
                import traceback
                print(traceback.format_exc())
                sys.stdout.flush()
                continue
        
        if not dvh_data:
            print("Warning: No DVH data was calculated for any structure!")
        else:
            print(f"Successfully calculated DVH for {len(dvh_data)} structures")
        sys.stdout.flush()
        
        return dvh_data
        
    except Exception as e:
        print(f"Error in main DVH calculation: {str(e)}")
        import traceback
        print(traceback.format_exc())
        sys.stdout.flush()
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    print("\n=== New Upload Request ===")
    sys.stdout.flush()
    
    if 'rtdose' not in request.files or 'rtstruct' not in request.files:
        return jsonify({'error': 'Missing required files'}), 400
    
    rtdose_file = request.files['rtdose']
    rtstruct_file = request.files['rtstruct']
    
    if rtdose_file.filename == '' or rtstruct_file.filename == '':
        return jsonify({'error': 'No selected files'}), 400
    
    if not (allowed_file(rtdose_file.filename) and allowed_file(rtstruct_file.filename)):
        return jsonify({'error': 'Invalid file type'}), 400
    
    print(f"Processing files: RTDOSE={rtdose_file.filename}, RTSTRUCT={rtstruct_file.filename}")
    sys.stdout.flush()
    
    rtdose_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(rtdose_file.filename))
    rtstruct_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(rtstruct_file.filename))
    
    rtdose_file.save(rtdose_path)
    rtstruct_file.save(rtstruct_path)
    
    try:
        dvh_data = calculate_dvh(rtdose_path, rtstruct_path)
        return jsonify(dvh_data)
    except Exception as e:
        print(f"Error in upload handler: {str(e)}")
        sys.stdout.flush()
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up uploaded files
        try:
            os.remove(rtdose_path)
            os.remove(rtstruct_path)
        except Exception as e:
            print(f"Error cleaning up files: {str(e)}")
            sys.stdout.flush()

@app.route('/export', methods=['POST'])
def export_dvh():
    data = request.json
    selected_structures = data.get('structures', [])
    dvh_data = data.get('dvhData', {})
    
    # Create Excel file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    
    # Create a new workbook
    workbook = openpyxl.Workbook()
    overview_sheet = workbook.active
    overview_sheet.title = 'Overview'
    
    # Create overview sheet
    overview_headers = ['Structure', 'Volume (cm³)', 'Min Dose (Gy)', 'Max Dose (Gy)', 
                       'Mean Dose (Gy)', 'D100 (Gy)', 'D98 (Gy)', 'D95 (Gy)', 'D2cc (Gy)']
    
    # Write headers to overview
    for col, header in enumerate(overview_headers, 1):
        overview_sheet.cell(row=1, column=col, value=header)
    
    # Write data to overview
    for row, structure in enumerate(selected_structures, 2):
        if structure in dvh_data:
            overview_sheet.cell(row=row, column=1, value=structure)
            overview_sheet.cell(row=row, column=2, value=f"{dvh_data[structure]['volume']:.2f}")
            overview_sheet.cell(row=row, column=3, value=f"{dvh_data[structure]['min_dose']:.2f}")
            overview_sheet.cell(row=row, column=4, value=f"{dvh_data[structure]['max_dose']:.2f}")
            overview_sheet.cell(row=row, column=5, value=f"{dvh_data[structure]['mean_dose']:.2f}")
            overview_sheet.cell(row=row, column=6, value=f"{dvh_data[structure]['D100']:.2f}")
            overview_sheet.cell(row=row, column=7, value=f"{dvh_data[structure]['D98']:.2f}")
            overview_sheet.cell(row=row, column=8, value=f"{dvh_data[structure]['D95']:.2f}")
            overview_sheet.cell(row=row, column=9, value=f"{dvh_data[structure]['D2cc']:.2f}")
    
    # Auto-adjust overview column widths
    for col in overview_sheet.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        overview_sheet.column_dimensions[column].width = min(adjusted_width, 50)
    
    # For each structure, create a separate sheet with DVH data
    for structure in selected_structures:
        if structure in dvh_data:
            # Create safe sheet name (max 31 chars including prefix, only valid characters)
            safe_name = "".join(c for c in structure if c.isalnum() or c in (' ', '_', '-'))
            safe_name = safe_name.strip()
            if len(safe_name) > 26:  # Leave room for 'dvh_' prefix
                safe_name = safe_name[:26]
            sheet_name = f"dvh_{safe_name}"
            
            # Ensure unique sheet name
            base_name = sheet_name
            counter = 1
            while sheet_name in workbook.sheetnames:
                sheet_name = f"{base_name[:22]}_{counter}"  # Leave room for counter
                counter += 1
            
            # Create worksheet
            worksheet = workbook.create_sheet(title=sheet_name)
            
            # Add statistics
            stats_rows = [
                ['Parameter', 'Value'],
                ['Structure', structure],
                ['Volume (cm³)', f"{dvh_data[structure]['volume']:.2f}"],
                ['Min Dose (Gy)', f"{dvh_data[structure]['min_dose']:.2f}"],
                ['Max Dose (Gy)', f"{dvh_data[structure]['max_dose']:.2f}"],
                ['Mean Dose (Gy)', f"{dvh_data[structure]['mean_dose']:.2f}"],
                ['D100 (Gy)', f"{dvh_data[structure]['D100']:.2f}"],
                ['D98 (Gy)', f"{dvh_data[structure]['D98']:.2f}"],
                ['D95 (Gy)', f"{dvh_data[structure]['D95']:.2f}"],
                ['D2cc (Gy)', f"{dvh_data[structure]['D2cc']:.2f}"]
            ]
            
            # Write statistics
            for row_idx, row_data in enumerate(stats_rows, 1):
                for col_idx, value in enumerate(row_data, 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx, value=value)
            
            # Add a blank row
            current_row = len(stats_rows) + 2
            
            # Write DVH data headers
            worksheet.cell(row=current_row, column=1, value='Dose (Gy)')
            worksheet.cell(row=current_row, column=2, value='Volume (%)')
            
            # Write DVH data
            doses = dvh_data[structure]['doses']
            volumes = dvh_data[structure]['volumes']
            
            for idx, (dose, volume) in enumerate(zip(doses, volumes)):
                current_row = len(stats_rows) + 3 + idx
                worksheet.cell(row=current_row, column=1, value=f"{dose:.2f}")
                worksheet.cell(row=current_row, column=2, value=f"{volume:.2f}")
            
            # Auto-adjust column widths
            for col in worksheet.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column].width = min(adjusted_width, 50)
    
    # Save the workbook
    workbook.save(temp_file.name)
    
    return send_file(
        temp_file.name,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='dvh_data.xlsx'
    )

if __name__ == '__main__':
    print("Starting Flask application...")
    sys.stdout.flush()
    app.run(debug=True)
