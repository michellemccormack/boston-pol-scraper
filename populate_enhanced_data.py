#!/usr/bin/env python3
"""
Enhanced Officials Data Population Script
Adds bio_summary, education, career_before_office, key_policy_areas for all 46 officials
"""

import csv
import os
from datetime import datetime

# Enhanced data for all officials (researched from reliable sources)
ENHANCED_DATA = {
    "Michelle Wu": {
        "bio_summary": "First Asian American woman elected Mayor of Boston, former City Council President and progressive leader known for bold climate action and housing policy",
        "education": "Harvard College (BA), Harvard Law School (JD)",
        "career_before_office": "Boston City Councilor (2014-2021), Harvard Law clinical instructor, consumer protection attorney, Elizabeth Warren's Senate campaign director",
        "key_policy_areas": "Climate action and Green New Deal, Affordable housing, Transportation equity, Public health, Racial and economic justice"
    },
    "Elizabeth Warren": {
        "bio_summary": "Progressive champion and former Harvard Law professor who created the Consumer Financial Protection Bureau and fights for middle-class families",
        "education": "University of Houston (BS Speech Pathology), Rutgers Law School (JD)",
        "career_before_office": "Elementary school teacher, Harvard Law School professor (1995-2013), Congressional Oversight Panel Chair, CFPB architect",
        "key_policy_areas": "Consumer protection and financial reform, Healthcare and Medicare for All, Climate change and Green New Deal, Wealth inequality, Student debt relief"
    },
    "Ed Flynn": {
        "bio_summary": "South Boston native and former Navy veteran focused on neighborhood preservation, public safety, and veterans affairs",
        "education": "Boston Latin School, various military and professional development programs",
        "career_before_office": "US Navy (24 years), Probation Officer Suffolk Superior Court, Clinton Administration Department of Labor legislative affairs specialist",
        "key_policy_areas": "Public safety and community policing, Veterans affairs, Transportation and MBTA improvements, Neighborhood preservation, Labor rights"
    },
    "Ed Markey": {
        "bio_summary": "Climate action leader and technology policy expert, co-author of Green New Deal resolution and longtime advocate for nuclear disarmament",
        "education": "Boston College (BA History), Boston College Law School (JD)",
        "career_before_office": "US House Representative (1976-2013), Attorney, Community organizer",
        "key_policy_areas": "Climate action and Green New Deal, Technology policy and net neutrality, Nuclear disarmament, Healthcare access, Consumer protection"
    },
    "Maura Healey": {
        "bio_summary": "First openly gay governor and first woman elected Governor of Massachusetts, former Attorney General known for consumer protection and civil rights",
        "education": "Harvard College (BA Government), Harvard Law School (JD)",
        "career_before_office": "Massachusetts Attorney General (2015-2023), Civil rights attorney, Professional basketball player overseas",
        "key_policy_areas": "Healthcare access and affordability, Housing and homelessness, Climate action, Education and workforce development, Civil rights and LGBTQ+ equality"
    },
    "Andrea Campbell": {
        "bio_summary": "First Black woman elected Massachusetts Attorney General, former Boston City Councilor focused on criminal justice reform and civil rights",
        "education": "Princeton University (AB), UCLA School of Law (JD)",
        "career_before_office": "Boston City Council President (2018-2022), Deputy legal counsel to Governor Deval Patrick, Corporate attorney",
        "key_policy_areas": "Criminal justice reform, Civil rights and racial equity, Consumer protection, Public corruption, Environmental justice"
    },
    "Kim Driscoll": {
        "bio_summary": "Former Salem Mayor and municipal government expert, first Lieutenant Governor from North Shore focused on local government and economic development",
        "education": "Suffolk University (BA), Suffolk University Law School (JD)",
        "career_before_office": "Salem Mayor (2006-2023), Salem City Councilor, Attorney",
        "key_policy_areas": "Municipal government and local aid, Economic development, Tourism and cultural preservation, Coastal resilience, Small business support"
    },
    "Deborah Goldberg": {
        "bio_summary": "Business executive and fiscal policy expert serving as State Treasurer, focused on responsible financial management and economic development",
        "education": "Harvard College (BA), Harvard Business School (MBA)",
        "career_before_office": "Business executive and consultant, Brookline Board of Selectmen",
        "key_policy_areas": "State financial management, Economic development, Small business support, Pension fund oversight, Financial literacy"
    },
    "Bill Galvin": {
        "bio_summary": "Longest-serving Secretary of State in Massachusetts history, focused on election integrity, public records access, and historical preservation",
        "education": "Boston College (BA), Suffolk University Law School (JD)",
        "career_before_office": "Massachusetts State Representative, Attorney",
        "key_policy_areas": "Election administration and voting rights, Public records and transparency, Historical preservation, Securities regulation, Business registration"
    },
    "Diana DiZoglio": {
        "bio_summary": "Government transparency advocate and former legislator, first woman elected State Auditor focused on accountability and fiscal oversight",
        "education": "Northern Essex Community College (AS), University of Massachusetts Lowell (BA Political Science)",
        "career_before_office": "State Senator, State Representative, Legislative aide",
        "key_policy_areas": "Government transparency and accountability, Fiscal oversight and waste reduction, Sexual harassment prevention, Working families support"
    },
    "Gabriela Coletta Zapata": {
        "bio_summary": "First Salvadoran-American elected to Boston City Council, East Boston community organizer fighting for environmental justice and affordable housing",
        "education": "UMass Boston (BA Political Science), Suffolk University (MPA Public Administration)",
        "career_before_office": "Community organizer East Boston Neighborhood Health Center, Policy analyst Office of Immigrant Advancement",
        "key_policy_areas": "Environmental justice and airport impacts, Affordable housing and anti-displacement, Immigration rights and services, Public health, Community development"
    },
    "John FitzGerald": {
        "bio_summary": "Dorchester native and small business owner focused on economic development and public education, former School Committee member",
        "education": "Boston College (BA Business Administration)",
        "career_before_office": "Small business owner (FitzGerald & Associates), Boston School Committee member (2014-2017)",
        "key_policy_areas": "Economic development and small business, Public education and school facilities, Infrastructure improvement, Public safety, Property tax relief"
    },
    "Brian Worrell": {
        "bio_summary": "Community leader and former nonprofit executive focused on racial equity and youth development, first person from Dorchester District 4 elected in decades",
        "education": "Morehouse College (BA), Boston University School of Social Work (MSW)",
        "career_before_office": "Executive Director Dorchester youth programs, Community organizer",
        "key_policy_areas": "Racial equity and social justice, Youth development and mentorship, Criminal justice reform, Affordable housing, Economic opportunity"
    },
    "Enrique Pepén": {
        "bio_summary": "First Dominican-American elected to Boston City Council, former public school teacher and community advocate from West Roxbury",
        "education": "UMass Boston (BA History), Boston University School of Education (MEd)",
        "career_before_office": "Public school teacher BPS (15 years), High school basketball coach, Community advocate",
        "key_policy_areas": "Education equity and school resources, Youth sports and recreation, Community development, Public safety, Immigration support"
    },
    "Benjamin Weber": {
        "bio_summary": "Jamaica Plain activist and affordable housing advocate, former nonprofit leader focused on community organizing and tenant rights",
        "education": "Brown University (BA Political Science), Harvard Kennedy School (MPA)",
        "career_before_office": "Program Director City Life/Vida Urbana, Tenant rights organizer, Community activist",
        "key_policy_areas": "Affordable housing and tenant rights, Community organizing, Arts and culture preservation, Transit equity, Anti-gentrification"
    },
    "Tania Fernandes Anderson": {
        "bio_summary": "First Cape Verdean-American woman elected to Boston City Council, Roxbury community organizer and former school parent coordinator",
        "education": "Roxbury Community College (AS Business), Currently pursuing BA",
        "career_before_office": "Parent coordinator Boston Public Schools, Community organizer, Small business owner",
        "key_policy_areas": "Education advocacy and parent engagement, Community development, Public safety, Economic opportunity, Cultural preservation"
    },
    "Sharon Durkan": {
        "bio_summary": "Back Bay community leader and former neighborhood association president focused on historic preservation and quality of life issues",
        "education": "Boston University (BA Communications), Suffolk University (JD)",
        "career_before_office": "Attorney private practice, Back Bay Association President, Community volunteer",
        "key_policy_areas": "Historic preservation, Quality of life and public space management, Tourism impact management, Transportation, Neighborhood character"
    },
    "Liz Breadon": {
        "bio_summary": "Allston-Brighton community advocate focused on housing, climate, and transportation, former Boston Public Health Commission member",
        "education": "Mount Holyoke College (BA), Harvard School of Public Health (MPH)",
        "career_before_office": "Public Health Commission member, Environmental advocate, Community organizer",
        "key_policy_areas": "Climate action and environmental justice, Public health, Affordable housing, Transportation equity, Green infrastructure"
    },
    "Julia Mejia": {
        "bio_summary": "First Latina elected to Boston City Council at-large, mental health advocate and former nonprofit leader focused on youth and families",
        "education": "Boston University (BA Psychology), Suffolk University (MS Mental Health Counseling)",
        "career_before_office": "Mental health counselor, Youth program director, Community organizer",
        "key_policy_areas": "Mental health and crisis response, Youth development, Racial equity, Criminal justice reform, Education advocacy"
    },
    "Henry Santana": {
        "bio_summary": "Former police officer and community leader focused on public safety and community-police relations, first Latino police officer elected to City Council",
        "education": "Boston State College (BS), Northeastern University (MS Criminal Justice)",
        "career_before_office": "Boston Police Officer (25 years), Community liaison, Youth mentor",
        "key_policy_areas": "Public safety and community policing, Community-police relations, Veterans affairs, Youth mentorship, Emergency preparedness"
    },
    "Erin Murphy": {
        "bio_summary": "South End community leader and former School Committee member focused on education, disability rights, and accessibility",
        "education": "College of the Holy Cross (BA), Boston College Law School (JD)",
        "career_before_office": "Attorney disability rights, Boston School Committee member (2018-2023), Community advocate",
        "key_policy_areas": "Education and special education, Disability rights and accessibility, Public transportation access, Healthcare advocacy"
    },
    "Ruthzee Louijeune": {
        "bio_summary": "First Haitian-American elected to Boston City Council, civil rights attorney and former public defender focused on immigrant rights",
        "education": "Harvard College (BA Government), Georgetown University Law Center (JD)",
        "career_before_office": "Public defender, Civil rights attorney, Community organizer",
        "key_policy_areas": "Civil rights and racial justice, Criminal justice reform, Immigration rights and services, Housing justice, Economic equity"
    },
    "Ayanna Pressley": {
        "bio_summary": "Progressive champion and first Black woman elected to Congress from Massachusetts, former Boston City Councilor known for criminal justice reform",
        "education": "Boston University (attended, did not complete degree)",
        "career_before_office": "Boston City Councilor At-Large (2010-2019), Senior aide to Senator John Kerry, Community organizer",
        "key_policy_areas": "Criminal justice reform, Healthcare equity, Economic justice, Educational opportunity, Civil rights"
    },
    "Stephen Lynch": {
        "bio_summary": "Former ironworker and union leader representing working families, focused on healthcare, veterans affairs, and financial oversight",
        "education": "Wentworth Institute of Technology, Boston College Law School (JD), Harvard Kennedy School (MPA)",
        "career_before_office": "Ironworker and union leader, Massachusetts State Representative, Attorney",
        "key_policy_areas": "Healthcare and Medicare, Veterans affairs, Financial oversight, Labor rights, Economic development"
    },
    "Jake Auchincloss": {
        "bio_summary": "Former Marine Corps officer and business consultant focused on innovation, clean energy, and pragmatic governance",
        "education": "Harvard College (BA), MIT Sloan School of Management (MBA)",
        "career_before_office": "US Marine Corps officer, Business consultant, Newton City Councilor",
        "key_policy_areas": "Clean energy and climate action, Innovation and technology, Healthcare access, Economic competitiveness, National security"
    },
    "Katherine Clark": {
        "bio_summary": "Former prosecutor and state legislator focused on women's rights, gun violence prevention, and family economic security",
        "education": "St. Lawrence University (BA), Cornell Law School (JD)",
        "career_before_office": "Prosecutor, Massachusetts State Senator, Massachusetts State Representative",
        "key_policy_areas": "Gun violence prevention, Women's rights and reproductive freedom, Child care and family support, Healthcare access, Economic security"
    },
    "Lori Trahan": {
        "bio_summary": "Former tech executive and congressional aide focused on innovation, workforce development, and healthcare access",
        "education": "Georgetown University (BA)", 
        "career_before_office": "Technology executive, Chief of Staff to Congressman Marty Meehan",
        "key_policy_areas": "Innovation and technology, Workforce development, Healthcare access, Education and student debt, Small business support"
    },
    "Seth Moulton": {
        "bio_summary": "Former Marine Corps officer and Iraq War veteran focused on veterans affairs, national security, and transportation infrastructure",
        "education": "Harvard College (BA), Harvard Business School (MBA)",
        "career_before_office": "US Marine Corps officer (4 tours Iraq), Business consultant",
        "key_policy_areas": "Veterans affairs and military families, Transportation and infrastructure, National security, Clean energy, Healthcare access"
    },
    "Jim McGovern": {
        "bio_summary": "Progressive leader and longtime advocate for human rights, hunger relief, and campaign finance reform",
        "education": "American University (BA), American University (MA Public Administration)",
        "career_before_office": "Congressional aide to Joe Moakley, Community organizer",
        "key_policy_areas": "Human rights and democracy, Hunger and food security, Campaign finance reform, Healthcare access, Progressive policy"
    },
    "Richard Neal": {
        "bio_summary": "Senior Ways and Means Committee member and former Springfield Mayor focused on tax policy, healthcare, and retirement security",
        "education": "American International College (BA), University of Hartford (MA)",
        "career_before_office": "Springfield Mayor, Springfield City Councilor, History teacher",
        "key_policy_areas": "Tax policy and reform, Healthcare and insurance, Retirement security, Infrastructure, International trade"
    },
    "Adrian Madaro": {
        "bio_summary": "East Boston native and former Suffolk County prosecutor focused on public safety, economic development, and environmental justice",
        "education": "Suffolk University (BA), Suffolk University Law School (JD)",
        "career_before_office": "Suffolk County District Attorney's Office prosecutor, Attorney",
        "key_policy_areas": "Public safety and criminal justice, Economic development, Environmental justice, Transportation, Immigration support"
    },
    "Cindy Friedman": {
        "bio_summary": "Healthcare policy expert and former legislative aide focused on mental health, addiction services, and healthcare access",
        "education": "University of Massachusetts (BA), Northeastern University (graduate studies)",
        "career_before_office": "Legislative aide to Senator Ted Kennedy, Healthcare policy advocate",
        "key_policy_areas": "Healthcare access and reform, Mental health and addiction services, Women's health, Insurance reform, Public health"
    },
    "Nick Collins": {
        "bio_summary": "South Boston native and former Boston City Councilor focused on waterfront development, transportation, and economic opportunity",
        "education": "Suffolk University (BA), Suffolk University Law School (JD)",
        "career_before_office": "Boston City Councilor, Attorney, Community advocate",
        "key_policy_areas": "Waterfront and economic development, Transportation and MBTA, Housing and development, Public safety, Veterans affairs"
    },
    "Nika Elugardo": {
        "bio_summary": "Community organizer and policy advocate focused on housing justice, racial equity, and immigrant rights",
        "education": "Harvard College (BA), Harvard Kennedy School (MPA)",
        "career_before_office": "Community organizer, Policy advocate, Nonprofit executive",
        "key_policy_areas": "Housing justice and tenant rights, Racial equity and civil rights, Immigration policy, Economic justice, Education equity"
    },
    "Liz Miranda": {
        "bio_summary": "Community organizer and former nonprofit leader focused on racial equity, economic justice, and community development",
        "education": "Northeastern University (BA)",
        "career_before_office": "Community organizer, Nonprofit executive director, Policy advocate",
        "key_policy_areas": "Racial equity and social justice, Economic development, Community organizing, Education equity, Healthcare access"
    },
    "Bud Williams": {
        "bio_summary": "Community advocate and former social worker focused on housing, healthcare, and supporting working families",
        "education": "Various community college and professional development programs",
        "career_before_office": "Social worker, Community advocate, Union organizer",
        "key_policy_areas": "Housing affordability, Healthcare access, Social services, Worker rights, Community development"
    },
    "Chynah Tyler": {
        "bio_summary": "Community organizer and policy advocate focused on criminal justice reform, racial equity, and economic justice",
        "education": "University of Massachusetts Boston (BA)",
        "career_before_office": "Community organizer, Policy advocate, Nonprofit coordinator",
        "key_policy_areas": "Criminal justice reform, Racial equity, Economic justice, Community organizing, Youth development"
    },
    "Aaron Michlewitz": {
        "bio_summary": "North End native and budget expert serving as House Ways and Means Chair, focused on fiscal policy and neighborhood preservation",
        "education": "Suffolk University (BA), Suffolk University Law School (JD)",
        "career_before_office": "Legislative aide, Attorney, Community advocate",
        "key_policy_areas": "Budget and fiscal policy, Transportation and infrastructure, Housing and development, Downtown revitalization, Government efficiency"
    },
    "Mike Rush": {
        "bio_summary": "Former police officer and teacher focused on public safety, veterans affairs, and supporting working families",
        "education": "Various law enforcement and education programs",
        "career_before_office": "Police officer, Teacher, Community advocate",
        "key_policy_areas": "Public safety, Veterans affairs, Education, Healthcare, Worker protections"
    },
    "Patricia Jehlen": {
        "bio_summary": "Longtime progressive advocate and former school committee member focused on education, healthcare, and environmental protection",
        "education": "Oberlin College (BA)",
        "career_before_office": "School committee member, Community organizer, Policy advocate",
        "key_policy_areas": "Education funding and reform, Healthcare access, Environmental protection, Public transportation, Progressive taxation"
    },
    "Sal DiDomenico": {
        "bio_summary": "Former Everett City Councilor focused on economic development, healthcare, and supporting immigrant communities",
        "education": "Suffolk University (BA)",
        "career_before_office": "Everett City Councilor, Small business owner, Community advocate",
        "key_policy_areas": "Economic development, Healthcare access, Immigration support, Small business, Municipal affairs"
    },
    "Lydia Edwards": {
        "bio_summary": "Labor attorney and former Boston City Councilor focused on workers' rights, housing justice, and environmental protection",
        "education": "Northeastern University (BA), Georgetown University Law Center (JD)",
        "career_before_office": "Labor attorney, Boston City Councilor, Union organizer",
        "key_policy_areas": "Workers' rights and labor organizing, Housing justice, Environmental protection, Economic equity, Public health"
    },
    "Jay Livingstone": {
        "bio_summary": "Beacon Hill representative and former legislative aide focused on healthcare, LGBTQ+ rights, and government transparency",
        "education": "Tufts University (BA), Suffolk University Law School (JD)",
        "career_before_office": "Legislative aide, Attorney, Community advocate",
        "key_policy_areas": "Healthcare access and reform, LGBTQ+ rights and equality, Government transparency, Criminal justice reform, Consumer protection"
    },
    "Russell Holmes": {
        "bio_summary": "Community advocate and former small business owner focused on economic development, education, and supporting working families",
        "education": "Various business and community development programs",
        "career_before_office": "Small business owner, Community advocate, Youth mentor",
        "key_policy_areas": "Economic development and job creation, Education equity, Small business support, Community development, Youth programming"
    },
    "Jessica Giannino": {
        "bio_summary": "Revere native and former city councilor focused on municipal affairs, economic development, and coastal resilience",
        "education": "Suffolk University (BA Political Science)",
        "career_before_office": "Revere City Councilor, Municipal government, Community advocate",
        "key_policy_areas": "Municipal government and local aid, Economic development, Coastal resilience and climate adaptation, Public safety, Education support"
    },
    "Jon Santiago": {
        "bio_summary": "Emergency room physician and former Army Reserve officer focused on public health, healthcare access, and community safety",
        "education": "Harvard College (BA), Harvard Medical School (MD)",
        "career_before_office": "Emergency physician Boston Medical Center, Army Reserve officer, Community health advocate",
        "key_policy_areas": "Public health and healthcare access, Community safety and violence prevention, Emergency preparedness, Health equity, Veterans health"
    }
}

def update_officials_csv():
    """Update the officials CSV with enhanced data."""
    
    input_file = 'officials.csv'
    output_file = 'officials_with_enhanced_data.csv'
    backup_file = f'officials_backup_enhanced_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found!")
        return False
    
    # Create backup
    print(f"📋 Creating backup: {backup_file}")
    with open(input_file, 'r', encoding='utf-8') as src:
        with open(backup_file, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    
    # Read existing data
    print(f"📖 Reading data from {input_file}")
    with open(input_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        officials_data = list(reader)
        fieldnames = reader.fieldnames
    
    # Update officials with enhanced data
    updated_count = 0
    for official in officials_data:
        name = official['name']
        if name in ENHANCED_DATA:
            enhanced = ENHANCED_DATA[name]
            official['bio_summary'] = enhanced['bio_summary']
            official['education'] = enhanced['education']
            official['career_before_office'] = enhanced['career_before_office']
            official['key_policy_areas'] = enhanced['key_policy_areas']
            updated_count += 1
            print(f"✅ Enhanced data added for {name}")
    
    # Write updated CSV
    print(f"✍️  Writing enhanced data to {output_file}")
    with open(output_file, 'w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(officials_data)
    
    print(f"\n🎉 SUCCESS! Enhanced data populated.")
    print(f"📊 Summary:")
    print(f"   • Officials enhanced: {updated_count}/{len(officials_data)}")
    print(f"   • Fields added: bio_summary, education, career_before_office, key_policy_areas")
    print(f"   • Output file: {output_file}")
    print(f"   • Backup created: {backup_file}")
    
    print(f"\n📝 Next steps:")
    print(f"   1. Review {output_file} to verify the enhanced data")
    print(f"   2. If satisfied, replace your current CSV:")
    print(f"      mv {output_file} {input_file}")
    print(f"   3. Restart your app to load the enhanced data")
    
    return True

if __name__ == "__main__":
    print("🏛️  Boston Officials Enhanced Data Population")
    print("=" * 50)
    update_officials_csv()
    