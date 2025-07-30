#!/usr/bin/env python3
"""
Safe CSV Enhancement Script
Adds new columns to officials.csv without modifying existing data
"""

import csv
import os
from datetime import datetime

def enhance_officials_csv():
    """
    Safely add new columns to officials.csv while preserving all existing data
    """
    
    # Input and output file paths
    input_file = 'officials.csv'
    output_file = 'officials_enhanced.csv'
    backup_file = f'officials_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    # New columns to add (with default empty values)
    new_columns = [
        'bio_summary',
        'education', 
        'career_before_office',
        'key_policy_areas',
        'committee_memberships',
        'recent_major_vote',
        'recent_initiative',
        'campaign_promises',
        'responsiveness_score',
        'town_halls_per_year',
        'office_hours'
    ]
    
    try:
        # Check if input file exists
        if not os.path.exists(input_file):
            print(f"❌ Error: {input_file} not found!")
            return False
        
        # Create backup of original file
        print(f"📋 Creating backup: {backup_file}")
        with open(input_file, 'r', encoding='utf-8') as src:
            with open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
        
        # Read existing CSV
        print(f"📖 Reading existing data from {input_file}")
        with open(input_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            existing_data = list(reader)
            existing_columns = reader.fieldnames
        
        print(f"✅ Found {len(existing_data)} officials with {len(existing_columns)} columns")
        
        # Create enhanced fieldnames (existing + new)
        enhanced_fieldnames = existing_columns + new_columns
        
        # Write enhanced CSV
        print(f"✍️  Writing enhanced data to {output_file}")
        with open(output_file, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=enhanced_fieldnames)
            writer.writeheader()
            
            for row in existing_data:
                # Add empty values for new columns
                for col in new_columns:
                    row[col] = ''  # Empty string as placeholder
                
                writer.writerow(row)
        
        print("🎉 SUCCESS! Enhanced CSV created.")
        print(f"\n📊 Summary:")
        print(f"   • Original file: {input_file} ({len(existing_columns)} columns)")
        print(f"   • Enhanced file: {output_file} ({len(enhanced_fieldnames)} columns)")
        print(f"   • Backup created: {backup_file}")
        print(f"   • Officials processed: {len(existing_data)}")
        
        print(f"\n🔍 New columns added:")
        for i, col in enumerate(new_columns, 1):
            print(f"   {i:2d}. {col}")
        
        print(f"\n📝 Next steps:")
        print(f"   1. Review {output_file} to verify your data looks correct")
        print(f"   2. If satisfied, replace {input_file} with {output_file}:")
        print(f"      mv {output_file} {input_file}")
        print(f"   3. Update your database schema in app.py")
        print(f"   4. Gradually fill in enhanced data over time")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def preview_changes():
    """
    Show a preview of what the enhancement will do
    """
    input_file = 'officials.csv'
    
    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found!")
        return
    
    print("🔍 PREVIEW MODE - No files will be modified")
    print("=" * 50)
    
    with open(input_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        existing_columns = reader.fieldnames
        sample_row = next(reader, None)
    
    new_columns = [
        'bio_summary', 'education', 'career_before_office',
        'key_policy_areas', 'committee_memberships', 'recent_major_vote',
        'recent_initiative', 'campaign_promises', 'responsiveness_score',
        'town_halls_per_year', 'office_hours'
    ]
    
    print(f"Current columns ({len(existing_columns)}):")
    for i, col in enumerate(existing_columns, 1):
        print(f"  {i:2d}. {col}")
    
    print(f"\nNew columns to add ({len(new_columns)}):")
    for i, col in enumerate(new_columns, 1):
        print(f"  {i:2d}. {col}")
    
    print(f"\nTotal after enhancement: {len(existing_columns) + len(new_columns)} columns")
    
    if sample_row:
        print(f"\nSample official: {sample_row.get('name', 'Unknown')}")
        print("✅ All existing data will be preserved exactly as-is")
        print("➕ New columns will be added with empty values for manual filling")

if __name__ == "__main__":
    print("🏛️  Boston Officials CSV Enhancement Tool")
    print("=" * 45)
    
    # Show preview first
    preview_changes()
    
    print("\n" + "=" * 45)
    response = input("Proceed with enhancement? (y/n): ").strip().lower()
    
    if response == 'y':
        enhance_officials_csv()
    else:
        print("👍 Operation cancelled. No files modified.")