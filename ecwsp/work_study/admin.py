#       Copyright 2010 Cristo Rey New York High School
#        Author David M Burke <david@burkesoftware.com>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

from ecwsp.work_study.models import *
from ecwsp.sis.models import *
from ecwsp.sis.admin import StudentFileInline
from reversion.admin import VersionAdmin
from django.http import HttpResponseRedirect
from django.contrib import admin
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType

from django import forms
from ecwsp.work_study.forms import StudentForm, WorkTeamForm
from ecwsp.sis.helper_functions import ReadPermissionModelAdmin
from ecwsp.administration.models import Configuration
from django.contrib.auth.models import User
from django.db.models import Q
from ajax_select import make_ajax_form
    
class StudentNumberInline(admin.TabularInline):
    model = StudentNumber
    extra = 1    
    
class CompContractInline(admin.TabularInline):
    model = CompContract
    extra = 0
    fields = ('contract_file', 'date', 'school_year', 'number_students', 'signed')

class CompanyHistoryInline(admin.TabularInline):
    model = CompanyHistory
    extra = 0
    max_num = 0

class CompanyAdmin(admin.ModelAdmin):
    def render_change_form(self, request, context, *args, **kwargs):
        try:
            workteams = WorkTeam.objects.filter(company=context['original'].id)
            txt = "<h5>Work teams:</h5>"
            for workteam in workteams:
                txt += "<a href=\"/admin/work_study/workteam/" + \
                    unicode(workteam.id) + "\" target=\"_blank\">" + unicode(workteam) + \
                    "</a><br/>"
            txt += "<h5>Current Students</h5>"
            students = StudentWorker.objects.filter(placement__company=context['original'].id)
            for student in students:
                txt += '<a href="/admin/work_study/studentworker/%s/" target="_blank"/> %s </a></br>' % (student.id, student,)
            txt += "<h5>Past Students</h5>"
            histories = CompanyHistory.objects.filter(placement__company=context['original'].id)
            for history in histories:
                txt += '%s </br>' % (history,)
            context['adminform'].form.fields['name'].help_text = txt
        except:
            print >> sys.stderr, "Error in company admin render_change_form"
        return super(CompanyAdmin, self).render_change_form(request, context, args, kwargs)
    search_fields = ('workteam__studentworker__fname', 'workteam__studentworker__lname', 'workteam__team_name')
    inlines = [CompContractInline]
admin.site.register(Company, CompanyAdmin)

class WorkTeamAdmin(VersionAdmin):
    form = WorkTeamForm
    
    def changelist_view(self, request, extra_context=None):
        """override to hide inactive workteams by default"""
        try:
            test = request.META['HTTP_REFERER'].split(request.META['PATH_INFO'])
            if test and test[-1] and not test[-1].startswith('?') and not request.GET.has_key('inactive__exact'):
                return HttpResponseRedirect("/admin/work_study/workteam/?inactive__exact=0")
        except: pass # In case there is no referer
        return super(WorkTeamAdmin,self).changelist_view(request, extra_context=extra_context)
    
    def render_change_form(self, request, context, *args, **kwargs):
        # only show login in group company    
        compUsers = User.objects.filter(Q(groups__name='company'))
        context['adminform'].form.fields['login'].queryset = compUsers
        try:
            students = StudentWorker.objects.filter(placement=context['original'].id)
            txt = "<h5>Students working here</h5>"
            for stu in students:
                txt += unicode(stu.edit_link() + '<br/>')
            txt += "<br/><br/><a href=\"/admin/work_study/timesheet/?company__id__exact=%s\" target=\"_blank\">Timesheets for company</a>" % \
                (context['original'].id) 
            txt += "<br/><a href=\"/admin/work_study/survey/?q=%s\" target=\"_blank\">Surveys for this company</a>" % \
                (context['original'].team_name)
            context['adminform'].form.fields['team_name'].help_text = txt
        except:
            print >> sys.stderr, "KeyError at /admin/work_study/company/add/  original"
        return super(WorkTeamAdmin, self).render_change_form(request, context, args, kwargs)
    
    def save_model(self, request, obj, form, change):
        super(WorkTeamAdmin, self).save_model(request, obj, form, change)
        form.save_m2m()
        group = Group.objects.get(name="company")
        for user in obj.login.all():
            user.groups.add(group)
            user.save()
    
    search_fields = ['company__name', 'team_name', 'address', 'cra__name__first_name', 'cra__name__last_name']
    list_filter = ['inactive', 'pickup_location', 'train_line', 'industry_type', 'paying',]
    fieldsets = [
        (None, {'fields': [('company', 'inactive'), 'team_name', 'job_description', 'company_description', 'login', ('paying', 'funded_by'), 'industry_type', 'cra', ('dropoff_location', 'pickup_location'), 'contacts']}),
        ("Location", {'fields': ['address', ('city', 'state'), 'zip',('train_line', 'stop_location'), ('map', 'use_google_maps'), 'directions_to', 'directions_pickup'], 'classes': ['collapse']}),
    ]
    filter_horizontal = ('contacts', 'login')
    list_display = ('team_name', 'company', 'stop_location', 'pickup_location', 'fte', 'paying', 'cra')
admin.site.register(WorkTeam, WorkTeamAdmin)

class CraContactAdmin(admin.ModelAdmin):
    search_fields = ['name__username', 'name__first_name', 'name__last_name']
admin.site.register(CraContact, CraContactAdmin)

class pickUpLocationAdmin(admin.ModelAdmin):
    search_fields = ['location']
admin.site.register(PickupLocation, pickUpLocationAdmin)

def increaseGradeLevel(modeladmin, request, queryset):
    for obj in queryset:
        obj.year = obj.year + 1
        obj.save()
increaseGradeLevel.shortDescription = "Increase grade level of selected students"
    
def approve(modeladmin, request, queryset):
    queryset.update(approved = True)
    for object in queryset:
        LogEntry.objects.log_action(
                    user_id         = request.user.pk, 
                    content_type_id = ContentType.objects.get_for_model(object).pk,
                    object_id       = object.pk,
                    object_repr     = unicode(object), 
                    action_flag     = CHANGE
                )
    
def move_to_former_students(modeladmin, request, queryset):
    for object in queryset:
        object.delete()

class StudentAdmin(ReadPermissionModelAdmin):
    form = StudentForm
    
    def changelist_view(self, request, extra_context=None):
        """override to hide inactive students by default"""
        try:
            test = request.META['HTTP_REFERER'].split(request.META['PATH_INFO'])
        except:
            test = None
        if test and test[-1] and not test[-1].startswith('?'):
            if not request.GET.has_key('inactive__exact'):
                q = request.GET.copy()
                q['inactive__exact'] = '0'
                request.GET = q
                request.META['QUERY_STRING'] = request.GET.urlencode()
        return super(StudentAdmin,self).changelist_view(request, extra_context=extra_context)
    
    def get_fieldsets(self, request, obj=None):
        "Hook for specifying fieldsets for the add form."
        if self.declared_fieldsets:
            fieldsets = self.declared_fieldsets
        else:
            form = self.get_form(request, obj)
            fieldsets = [(None, {'fields': form.base_fields.keys()})]
        for fs in fieldsets:
            fs[1]['fields'] = [f for f in fs[1]['fields'] if self.can_view_field(request, obj, f)]
        return fieldsets
    
    def get_form(self, request, obj=None):
        superclass = super(StudentAdmin, self)
        formclass = superclass.get_form(request, obj)
        for name, field in formclass.base_fields.items():
            if not request.user.is_superuser and name == "ssn":
                self.exclude = ('ssn',)
        return formclass
    
    def can_view_field(self, request, object, field_name):
        "Only allow superuser's to view ssn"
        if not request.user.is_superuser and field_name == "ssn":
            return False
        return True
    
    def render_change_form(self, request, context, *args, **kwargs):
        try:
            compContacts = Contact.objects.filter(workteam=context['original'].placement)
            context['adminform'].form.fields['primary_contact'].queryset = compContacts
            txt = context['adminform'].form.fields['placement'].help_text 
            txt += "<a href=\"/admin/work_study/timesheet/?q=%s+%s\" target=\"_blank\">Time Sheets for this student</a>" % \
                (context['original'].fname, context['original'].lname)
            txt += "<br/><a href=\"/admin/work_study/survey/?q=%s+%s\" target=\"_blank\">Surveys for this student</a>" % \
                (context['original'].fname, context['original'].lname)
            txt += "<br/>Go to work team " + str(context['original'].company())
            txt += "<br/>Company Contacts:"
            for compContact in compContacts:
                txt += "<br/>" + str(compContact.edit_link())
            context['adminform'].form.fields['placement'].help_text = txt
        except:
            print >> sys.stderr, "key error at student admin, maybe from creating a new student"
        return super(StudentAdmin, self).render_change_form(request, context, args, kwargs)
        
    fieldsets = [
        (None, {'fields': ['inactive', 'fname', 'lname', 'mname', 'sex', 'bday', 'day', 'fax',
                           'pic', 'unique_id', 'adp_number', 'ssn', 'username', 'work_permit_no',
                           'year', 'placement', 'school_pay_rate', 'student_pay_rate', 'primary_contact']}),
        ('Parent and address', {'fields': ['parent_guardian', 'emergency_contacts', 'street',
                                           'city', 'state', 'zip', 'parent_email', 'alt_email'],
            'classes': ['collapse']}),
        ('Personality', {'fields': ['personality_type', 'handout33'], 'classes': ['collapse']}),
    ]
    
    def get_readonly_fields(self, request, obj=None):
        edit_all = Configuration.get_or_default("Edit all Student Worker Fields", "False")
        if edit_all.value == "True":
            return ['parent_guardian', 'street', 'city', 'state', 'zip', 'parent_email', 'alt_email']
        return super(StudentAdmin, self).get_readonly_fields(request, obj=obj)

    inlines = [StudentNumberInline, StudentFileInline, CompanyHistoryInline]
    list_filter = ['day', 'year', 'inactive']
    list_display = ('fname', 'lname', 'day', 'company', 'pickUp', 'cra', 'primary_contact')
    filter_horizontal = ('handout33',)
    search_fields = ['fname', 'lname', 'unique_id', 'placement__team_name', 'username', 'id']
    readonly_fields = ['inactive', 'fname', 'lname', 'mname', 'sex', 'bday', 'username', 'year', 'parent_guardian', 'street', 'city', 'state', 'zip', 'parent_email', 'alt_email']    
admin.site.register(StudentWorker, StudentAdmin)

admin.site.register(PresetComment)

class StudentInteractionAdmin(admin.ModelAdmin):
    form = make_ajax_form(StudentInteraction, dict(student='studentworker'))
    
    list_display = ('students', 'date', 'type', 'cra', 'comment_Brief', 'reported_by')
    list_filter = ['type', 'date', 'student','student__inactive']
    search_fields = ['comments', 'student__fname', 'student__lname', 'type', 'companies__team_name', 'reported_by__first_name' , 'reported_by__last_name']
    filter_horizontal = ('preset_comment',)
    readonly_fields = ['companies', ]
    fields = ['type', 'student', 'comments', 'preset_comment','companies', 'reported_by']
    
    def lookup_allowed(self, lookup, *args, **kwargs):
        if lookup in ('student__student_ptr__exact'):
            return True
        return super(StudentInteractionAdmin, self).lookup_allowed(lookup, *args, **kwargs)
    
    def save_model(self, request, obj, form, change):
        obj.save()
        try:
            comp = WorkTeam.objects.get(id=obj.student.placement.id)
            cra = CraContact.objects.get(id=comp.cra.id)
            
            msg = str(obj.student) + " had a " + str(obj.get_type_display()) + " meeting on " + str(obj.date) + "\n" + str(obj.comments) + "\n" 
            for comment in obj.preset_comment.all():
                msg += str(comment) + "\n"
            
            send_mail(str(obj.get_type_display()) + " report: " + str(obj.student), msg, str(request.user.email), [cra.email])
        except:
            print >> sys.stderr, "could not send CRA email"
        
admin.site.register(StudentInteraction, StudentInteractionAdmin)

class ContactAdmin(admin.ModelAdmin):
    def render_change_form(self, request, context, *args, **kwargs):
        try:
            comps = WorkTeam.objects.filter(contacts=context['original'].id)
            txt = "Companies linked with"
            for comp in comps:
                txt += "<br/>" + str(comp.edit_link())
            context['adminform'].form.fields['lname'].help_text = txt
        except:
            print >> sys.stderr, "contact admin error, probably from making new one"
        return super(ContactAdmin, self).render_change_form(request, context, args, kwargs)
            
    search_fields = ['fname', 'lname']
    list_display = ('fname','lname',)
    exclude = ('guid',)
admin.site.register(Contact, ContactAdmin)

class TimeSheetAdmin(admin.ModelAdmin):
    def render_change_form(self, request, context, *args, **kwargs):
        try:
            txt = context['original'].student.primary_contact
            context['adminform'].form.fields['supervisor_comment'].help_text = txt
            return super(TimeSheetAdmin, self).render_change_form(request, context, args, kwargs)
        except: 
            return super(TimeSheetAdmin, self).render_change_form(request, context, args, kwargs)
        
    search_fields = ['student__fname', 'student__lname', 'company__team_name']
    list_filter = ['date', 'creation_date', 'approved', 'for_pay', 'make_up', 'company', 'student__inactive']
    list_display = ('student', 'date', 'company', 'performance', 'student_Accomplishment_Brief', 'supervisor_Comment_Brief', 'approved', 'for_pay', 'make_up',)
    readonly_fields = ['supervisor_key', 'hours', 'school_net', 'student_net', 'creation_date']
    actions = [approve]
admin.site.register(TimeSheet, TimeSheetAdmin)

admin.site.register(CompanyHistory)

class AttendanceAdmin(admin.ModelAdmin):
    form = make_ajax_form(Attendance, dict(student='studentworker'))
    search_fields = ['student__fname', 'student__lname', 'absence_date']
    list_filter = ['absence_date', 'makeup_date', 'reason', 'fee', 'student']
    list_display = ('absence_date', 'makeup_date', 'reason', 'fee', 'student')
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(AttendanceFee)
admin.site.register(AttendanceReason)
admin.site.register(Personality)
admin.site.register(Handout33)

class ClientVisitAdmin(admin.ModelAdmin):
    form = make_ajax_form(ClientVisit, dict(student_worker='studentworker', supervisor='company_contact'))
    fieldsets = [
        (None, {'fields': ['date', 'company', 'notify_mentors', 'notes',]}),
        ("DOL", {'fields': ['dol', 'follow_up_of', 'cra', 'student_worker', 'supervisor',
                            'attendance_and_punctuality', 'attitude_and_motivation',
                            'productivity_and_time_management', 'ability_to_learn_new_tasks',
                            'professional_appearance', 'interaction_with_coworkers',
                            'initiative_and_self_direction', 'accuracy_and_attention_to_detail',
                            'organizational_skills', 'observations', 'supervisor_comments',
                            'student_comments', 'job_description', 'work_environment'],
            'classes': ['collapse']}),
    ]
    search_fields = ['company__team_name', 'notes']
    list_display = ('company', 'date', 'comment_brief', 'student_worker')
    list_filter = ['date', 'company']
admin.site.register(ClientVisit, ClientVisitAdmin)

class SurveyAdmin(admin.ModelAdmin):
    search_fields = ['student__fname', 'student__lname','survey','question','answer','company__team_name']
    list_display = ('survey', 'student', 'question', 'answer', 'date', 'company')
    list_filter = ['survey','question']
admin.site.register(Survey, SurveyAdmin)
admin.site.register(PaymentOption)
admin.site.register(StudentDesiredSkill)
admin.site.register(StudentFunctionalResponsibility)

class CompContractAdmin(admin.ModelAdmin):
    list_display = ('company', 'name', 'signed', 'date', 'number_students')
    list_filter = ('signed','date',)
    search_fields = ('company__name', 'name')
admin.site.register(CompContract, CompContractAdmin)