# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
#from bs4 import BeautifulSoup
import openerp.tools
import re
import time
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

class scrum_sprint(models.Model):
    _name = 'project.scrum.sprint'
    _description = 'Project Scrum Sprint'
    _order = 'date_start desc'

    def _compute(self):
        for record in self:
            if record.date_start and record.date_stop:
                record.progress = float((date.today() - fields.Date.from_string(record.date_start)).days) / float(record.time_cal()) * 100
                if date.today() >= fields.Date.from_string(record.date_stop):
                    record.date_duration = record.time_cal() * 9
                else:
                    record.date_duration = (date.today() - fields.Date.from_string(record.date_start)).days * 9
            else:
                record.date_duration = 0
                
    def _compute_progress(self):
        for record in self:
            if record.planned_hours and record.effective_hours and record.planned_hours != 0:
                record.progress = record.effective_hours / record.planned_hours * 100
            else:
                record.progress = 0

    def time_cal(self):
        diff = fields.Date.from_string(self.date_stop) - fields.Date.from_string(self.date_start)
        if diff.days <= 0:
            return 1
        return diff.days + 1
            
    def test_task(self, cr, uid, sprint, pool):
        tags = pool.get('project.category').search(cr,uid,[('name', '=', 'test')])  # search tags with name "test"
        if len(tags)==0:    # if not exist, then creat a "test" tag into category
            tags.append(pool.get('project.category').create(cr,uid,{'name':'test'}))
        for tc in sprint.project_id.test_case_ids:  # loop through each test cases to creat task
            pool.get('project.task').create(cr, uid,{
                'name': '[TC] %s' % tc.name,
                'description': tc.description_test,
                'project_id': tc.project_id.id,
                'sprint_id': sprint.id,
                'categ_ids': [(6,_,tags)],
                })

    #def _task_count(self):    # method that calculate how many tasks exist
        #for p in self:
            #p.task_count = len(p.task_ids)
    
    #def _task_test_count(self):    # method that calculate how many tasks in testing exist
        #task = self.env['project.task'].search([('categ_ids','ilike','test')])
        #for p in self:
            #p.task_test_count = len(p.task_test_ids)

    name = fields.Char(string = 'Sprint Name', required=True)
    meeting_ids = fields.One2many(comodel_name = 'project.scrum.meeting', inverse_name = 'sprint_id', string ='Daily Scrum')
    user_id = fields.Many2one(comodel_name='res.users', string='Assigned to')
    date_start = fields.Date(string = 'Starting Date', default=fields.Date.today())
    date_stop = fields.Date(string = 'Ending Date')
    date_duration = fields.Integer(compute = '_compute', string = 'Duration(in hours)')
    description = fields.Text(string = 'Description', required=False)
    project_id = fields.Many2one(comodel_name = 'project.project', string = 'Project', ondelete='set null', select=True, track_visibility='onchange',
        change_default=True, required=True, help="If you have [?] in the project name, it means there are no analytic account linked to this project.")
    product_owner_id = fields.Many2one(comodel_name = 'res.users', string = 'Product Owner', required=False,help="The person who is responsible for the product")
    scrum_master_id = fields.Many2one(comodel_name = 'res.users', string = 'Scrum Master', required=False,help="The person who is maintains the processes for the product")
    us_ids = fields.One2many(comodel_name = 'project.scrum.us', inverse_name = 'sprint_id', string = 'User Stories')
    task_ids = fields.One2many(comodel_name = 'project.task', inverse_name = 'sprint_id')
    #task_count = fields.Integer(compute = '_task_count')
    #task_test_count = fields.Integer(compute = '_task_test_count')
    review = fields.Html(string = 'Sprint Review', default="""
        <h1 style="color:blue"><ul>What was the goal of this sprint?</ul></h1><br/><br/>
        <h1 style="color:blue"><ul>Does the goal have been reached?</ul></h1><br/><br/>
    """)
    retrospective = fields.Html(string = 'Sprint Retrospective', default="""
        <h1 style="color:blue"><ul>What will you start doing in next sprint?</ul></h1><br/><br/>
        <h1 style="color:blue"><ul>What will you stop doing in next sprint?</ul></h1><br/><br/>
        <h1 style="color:blue"><ul>What will you continue doing in next sprint?</ul></h1><br/><br/>
    """)
    sequence = fields.Integer('Sequence', help="Gives the sequence order when displaying a list of tasks.")
    progress = fields.Float(compute="_compute_progress", group_operator="avg", type='float', multi="progress", string='Progress (0-100)', help="Computed as: Time Spent / Total Time.")
    effective_hours = fields.Float(compute="_hours_get", multi="effective_hours", string='Effective hours', help="Computed using the sum of the task work done.")
    planned_hours = fields.Float(multi="planned_hours", string='Planned Hours', help='Estimated time to do the task, usually set by the project manager when the task is in draft state.')
    state = fields.Selection([('draft','Draft'),('open','Open'),('pending','Pending'),('cancel','Cancelled'),('done','Done')], string='State', required=False)
    company_id = fields.Many2one(related='project_id.analytic_account_id.company_id')

    # Compute: effective_hours, total_hours, progress
    @api.one
    def _hours_get(self):
        res = {}
        effective_hours = 0.0
        planned_hours = 0.0
        for task in self.task_ids:
            effective_hours += task.effective_hours or 0.0
            planned_hours += task.planned_hours or 0.0
        self.effective_hours = effective_hours
        # self.planned_hours = planned_hours
        return True
   
        
    @api.onchange('project_id')
    def onchange_project_id(self):
        if self.project_id and self.project_id.manhours:
            self.planned_hours = self.project_id.manhours
        else:
            self.planned_hours = 0.0

    @api.onchange('date_start')
    def onchange_date_start(self):
        if self.date_start:
            if self.project_id:
                self.date_stop = fields.Date.from_string(self.date_start) + timedelta(days=self.project_id.default_sprintduration)
        else:
            pass

class project_user_stories(models.Model):
    _name = 'project.scrum.us'
    _description = 'Project Scrum Use Stories'
    _order = 'sequence'

    name = fields.Char(string='User Story', required=True)
    color = fields.Integer('Color Index')
    description = fields.Html(string = 'Description')
    description_short = fields.Text(compute = '_conv_html2text')
    actor_ids = fields.Many2many(comodel_name='project.scrum.actors', string = 'Actor')
    project_id = fields.Many2one(comodel_name = 'project.project', string = 'Project', ondelete='set null',
        select=True, track_visibility='onchange', change_default=True)
    sprint_id = fields.Many2one(comodel_name = 'project.scrum.sprint', string = 'Sprint')
    task_ids = fields.One2many(comodel_name = 'project.task', inverse_name = 'us_id')
    task_test_ids = fields.One2many(comodel_name = 'project.scrum.test', inverse_name = 'user_story_id_test')
    task_count = fields.Integer(compute = '_task_count')
    test_ids = fields.One2many(comodel_name = 'project.scrum.test', inverse_name = 'user_story_id_test')
    test_count = fields.Integer(compute = '_test_count')
    sequence = fields.Integer('Sequence')
    company_id = fields.Many2one(related='project_id.analytic_account_id.company_id')
    #has_task = fields.Boolean()
    #has_test = fields.Boolean()
    
    @api.one
    def _conv_html2text(self):  # method that return a short text from description of user story
        for d in self: 
            d.description_short = re.sub('<.*>', ' ', d.description or '')
            if len(d.description_short)>=150:
                d.description_short = d.description_short[:149]
            #d.description_short = d.description_short[: len(d.description_short or '')-1 if len(d.description_short or '')<=150 else 149]
            #d.description_short = re.sub('<.*>', ' ', d.description)[:len(d.description) - 1 if len(d.description)>149 then 149]
            #d.description_short = BeautifulSoup(d.description.replace('*', ' ') or '').get_text()[:49] + '...'
        #self.description_short = BeautifulSoup(self.description).get_text()
            
    @api.multi
    def _task_count(self):    # method that calculate how many tasks exist
        for p in self:
            p.task_count = len(p.task_ids)
            
    def _test_count(self):    # method that calculate how many test cases exist
        for p in self:
            p.test_count = len(p.test_ids)

    def _resolve_project_id_from_context(self, cr, uid, context=None):
        """ Returns ID of project based on the value of 'default_project_id'
            context key, or None if it cannot be resolved to a single
            project.
        """
        if context is None:
            context = {}
        if type(context.get('default_project_id')) in (int, long):
            return context['default_project_id']
        if isinstance(context.get('default_project_id'), basestring):
            project_name = context['default_project_id']
            project_ids = self.pool.get('project.project').name_search(cr, uid, name=project_name, context=context)
            if len(project_ids) == 1:
                return project_ids[0][0]
        return None

    @api.model
    def _read_group_sprint_id(self, present_ids, domain, **kwargs):
        project_id = self._resolve_project_id_from_context()
        sprints = self.env['project.scrum.sprint'].search([('project_id', '=', project_id)], order='sequence').name_get()
        #sprints.sorted(key=lambda r: r.sequence)
        return sprints, None

    _group_by_full = {
        'sprint_id': _read_group_sprint_id,
        }
    name = fields.Char()

class project_task(models.Model):
    _inherit = "project.task"
    _order = "sequence"

    actor_ids = fields.Many2many(comodel_name='project.scrum.actors', string = 'Actor')
    sprint_id = fields.Many2one(comodel_name = 'project.scrum.sprint', string = 'Sprint')
    us_id = fields.Many2one(comodel_name = 'project.scrum.us', string = 'User Stories')
    date_start = fields.Date(string = 'Starting Date', required=False, default=date.today())
    date_end = fields.Date(string = 'Ending Date', required=False)
    use_scrum = fields.Boolean(related='project_id.use_scrum')
    
    @api.multi
    def write(self, vals):
        if vals.get('stage_id') == self.env.ref('project.project_tt_deployment').id:
            vals['date_end'] = fields.datetime.now()
        return super(project_task, self).write(vals)

    @api.model
    def _read_group_sprint_id(self, present_ids, domain, **kwargs):
        if self.use_scrum:
            project_id = self._resolve_project_id_from_context()
            sprints = self.env['project.scrum.sprint'].search([('project_id', '=', project_id)], order='sequence').name_get()
            #sprints.sorted(key=lambda r: r.sequence)
            return sprints, None
        else:
            return [], None

    @api.model
    def _read_group_us_id(self, present_ids, domain, **kwargs):
        if self.use_scrum:
            project_id = self._resolve_project_id_from_context()
            user_stories = self.env['project.scrum.us'].search([('project_id', '=', project_id)]).name_get()
            return user_stories, None
        else:
            return [], None

    #def _auto_init(self, cr, context=None):
        #self._group_by_full['sprint_id'] = _read_group_sprint_id
        #self._group_by_full['us_id'] = _read_group_us_id
        #super(project_task, self)._auto_init(cr, context)

    def _read_group_stage_ids(self, cr, uid, ids, domain, read_group_order=None, access_rights_uid=None, context=None):
        stage_obj = self.pool.get('project.task.type')
        order = stage_obj._order
        access_rights_uid = access_rights_uid or uid
        if read_group_order == 'stage_id desc':
            order = '%s desc' % order
        search_domain = []
        project_id = self._resolve_project_id_from_context(cr, uid, context=context)
        if project_id:
            search_domain += ['|', ('project_ids', '=', project_id)]
        search_domain += [('id', 'in', ids)]
        stage_ids = stage_obj._search(cr, uid, search_domain, order=order, access_rights_uid=access_rights_uid, context=context)
        result = stage_obj.name_get(cr, access_rights_uid, stage_ids, context=context)
        # restore order of the search
        result.sort(lambda x,y: cmp(stage_ids.index(x[0]), stage_ids.index(y[0])))

        fold = {}
        for stage in stage_obj.browse(cr, access_rights_uid, stage_ids, context=context):
            fold[stage.id] = stage.fold or False
        return result, fold

    def _read_group_user_id(self, cr, uid, ids, domain, read_group_order=None, access_rights_uid=None, context=None):
        res_users = self.pool.get('res.users')
        project_id = self._resolve_project_id_from_context(cr, uid, context=context)
        access_rights_uid = access_rights_uid or uid
        if project_id:
            ids += self.pool.get('project.project').read(cr, access_rights_uid, project_id, ['members'], context=context)['members']
            order = res_users._order
            # lame way to allow reverting search, should just work in the trivial case
            if read_group_order == 'user_id desc':
                order = '%s desc' % order
            # de-duplicate and apply search order
            ids = res_users._search(cr, uid, [('id','in',ids)], order=order, access_rights_uid=access_rights_uid, context=context)
        result = res_users.name_get(cr, access_rights_uid, ids, context=context)
        # restore order of the search
        result.sort(lambda x,y: cmp(ids.index(x[0]), ids.index(y[0])))
        return result, {}
    
    try:
        _group_by_full['sprint_id'] = _read_group_sprint_id
        _group_by_full['us_id'] = _read_group_us_id
    except:
        _group_by_full = {
            'sprint_id': _read_group_sprint_id,
            'us_id': _read_group_us_id,
            'stage_id': _read_group_stage_ids,
            'user_id': _read_group_user_id,
            
        }

class project_actors(models.Model):
    _name = 'project.scrum.actors'
    _description = 'Actors in user stories'

    name = fields.Char(string='Name', size=60)

class scrum_meeting(models.Model):
    _name = 'project.scrum.meeting'
    _description = 'Project Scrum Daily Meetings'
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    project_id = fields.Many2one(comodel_name = 'project.project', string = 'Project', ondelete='set null',
        select=True, track_visibility='onchange', change_default=True)
    sprint_id = fields.Many2one(comodel_name = 'project.scrum.sprint', string = 'Sprint')
    date_meeting = fields.Date(string = 'Date', required=True, default=date.today())
    user_id_meeting = fields.Many2one(comodel_name = 'res.users', string = 'Name', required=True, default=lambda self: self.env.user)
    question_yesterday = fields.Text(string = 'Description', required=True)
    question_today = fields.Text(string = 'Description', required=True)
    question_blocks = fields.Text(string = 'Description', required=True)
    question_backlog = fields.Selection([('yes','Yes'),('no','No')], string='Backlog Accurate?', required=False, default = 'yes')
    company_id = fields.Many2one(related='project_id.analytic_account_id.company_id')

    @api.multi
    def send_email(self):
        assert len(self) == 1, 'This option should only be used for a single id at a time.'
        template = self.env.ref('project_scrum.email_template_id', False)
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model='project.scrum.meeting',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template.id,
            default_composition_mode='comment',
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

class project(models.Model):
    _inherit = 'project.project'

    sprint_ids = fields.One2many(comodel_name = "project.scrum.sprint", inverse_name = "project_id", string = "Sprints")
    user_story_ids = fields.One2many(comodel_name = "project.scrum.us", inverse_name = "project_id", string = "User Stories")
    meeting_ids = fields.One2many(comodel_name = "project.scrum.meeting", inverse_name = "project_id", string = "Meetings")
    test_case_ids = fields.One2many(comodel_name = "project.scrum.test", inverse_name = "project_id", string = "Test Cases")  
    sprint_count = fields.Integer(compute = '_sprint_count', string="Sprints")
    user_story_count = fields.Integer(compute = '_user_story_count', string="User Stories")
    meeting_count = fields.Integer(compute = '_meeting_count', string="Meetings")
    test_case_count = fields.Integer(compute = '_test_case_count', string="Test Cases")
    use_scrum = fields.Boolean(store=True)
    default_sprintduration = fields.Integer(string = 'Calendar', required=False, default=14,help="Default Sprint time for this project, in days")
    manhours = fields.Integer(string = 'Man Hours', required=False,help="How many hours you expect this project needs before it's finished")
    

    def _sprint_count(self):    # method that calculate how many sprints exist
        for p in self:
            p.sprint_count = len(p.sprint_ids)

    def _user_story_count(self):    # method that calculate how many user stories exist
        for p in self:
            p.user_story_count = len(p.user_story_ids)

    def _meeting_count(self):    # method that calculate how many meetings exist
        for p in self:
            p.meeting_count = len(p.meeting_ids)
            
    def _test_case_count(self):    # method that calculate how many test cases exist
        for p in self:
            p.test_case_count = len(p.test_case_ids)

class test_case(models.Model):
    _name = 'project.scrum.test'
    _order = 'sequence_test'

    name = fields.Char(string='Name', required=True)
    color = fields.Integer('Color Index')
    project_id = fields.Many2one(comodel_name = 'project.project', string = 'Project', ondelete='set null', select=True, track_visibility='onchange', change_default=True)
    sprint_id = fields.Many2one(comodel_name = 'project.scrum.sprint', string = 'Sprint')
    user_story_id_test = fields.Many2one(comodel_name = "project.scrum.us", string = "User Story")
    description_test = fields.Html(string = 'Description')
    sequence_test = fields.Integer(string = 'Sequence', select=True)
    stats_test = fields.Selection([('draft','Draft'),('in progress','In Progress'),('cancel','Cancelled')], string='State', required=False)
    company_id = fields.Many2one(related='project_id.analytic_account_id.company_id')

    def _resolve_project_id_from_context(self, cr, uid, context=None):
        if context is None:
            context = {}
        if type(context.get('default_project_id')) in (int, long):
            return context['default_project_id']
        if isinstance(context.get('default_project_id'), basestring):
            project_name = context['default_project_id']
            project_ids = self.pool.get('project.project').name_search(cr, uid, name=project_name, context=context)
            if len(project_ids) == 1:
                return project_ids[0][0]
        return None

    @api.model
    def _read_group_us_id(self, present_ids, domain, **kwargs):
        project_id = self._resolve_project_id_from_context()
        user_stories = self.env['project.scrum.us'].search([('project_id', '=', project_id)]).name_get()
        return user_stories, None

    _group_by_full = {
        'user_story_id_test': _read_group_us_id,
        }
    name = fields.Char()
