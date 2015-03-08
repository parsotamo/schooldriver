from ecwsp.sis.num_utils import array_contains_anything
from ecwsp.sis.models import GradeScaleRule
from .models import Grade
import numpy as np
from constance import config


class GradeCalculator(object):
    def __init__(self, rounding=None):
        if rounding is None:
            self.rounding = config.GRADE_ROUNDING_DECIMAL
        else:
            self.rounding = None

    def _round(self, value):
        return np.round(
            value + 0.00000000000001,  # Work around floating point rounding
            decimals=self.rounding
        )

    def _calculate_course_grade(
        self, np_grade_values, np_final_grades, np_mp_weights,
        marking_periods=None
    ):
        if np_grade_values.size == 0:
            return None
        np_grade_values_mask = ~np.isnan(np_grade_values)
        # If marking periods are selected - don't return final override
        if not marking_periods and array_contains_anything(np_final_grades):
            average = np_final_grades[0]
        else:
            average = np.average(
                np_grade_values[np_grade_values_mask],
                weights=np_mp_weights[np_grade_values_mask])
        return average

    def _get_student_grades(self, student, date):
        """ Returns Grade queryset from student """
        grades = Grade.objects.filter(enrollment__user=student)
        if date is not None:
            grades = grades.filter(marking_period__end_date__lte=date)
        return grades

    def _get_enrollment_grades(self, enrollment, date):
        """ Returns Grade queryset from enrollment """
        grades = enrollment.grade_set.all()
        if date is not None:
            grades = grades.filter(marking_period__end_date__lte=date)
        return grades

    def _get_average_of_grades(self, grades):
        grades = grades.values_list(
            'grade',
            'marking_period',
            'marking_period__weight',
            'enrollment__course_section',
            'enrollment__finalgrade__grade',
        )
        if not grades:
            return None
        np_grades = np.array(grades, dtype=np.dtype(float))
        np_course_section = np_grades[:, 3]
        course_averages = []
        for course in np.unique(np_course_section):
            np_course_grades = np_grades[np.where(np_course_section == course)]
            np_grade_values = np_course_grades[:, 0]
            np_mp_weights = np_course_grades[:, 2]
            np_final_grades = np_course_grades[:, 4]
            course_averages += [self._calculate_course_grade(
                np_grade_values,
                np_final_grades,
                np_mp_weights,
            )]
        average = np.average(course_averages)
        return self._round(average)

    def get_course_grade(self, enrollment,
                         date=None,
                         marking_periods=None,
                         letter=False,
                         letter_and_number=False):
        """Get course final grade by calulating it or from override

        Args:
            enrollment: CourseEnrollment object
            date: Date of report - used to exclude grades that haven't happened
            marking_periods: Filter grades by these
            letter: Return letter grade from scale
            letter_and_number: Return string like 87.65 (B+)
        """
        grades = self._get_enrollment_grades(enrollment, date)
        if marking_periods is not None:
            grades = grades.filter(marking_period__in=marking_periods)
        grades = grades.values_list(
            'grade',
            'marking_period',
            'marking_period__weight',
            'enrollment__finalgrade__grade',
        )
        if not grades:
            return None
        np_grades = np.array(grades, dtype=np.dtype(float))
        np_grade_values = np_grades[:, 0]
        np_mp = np_grades[:, 1]
        np_mp_weights = np_grades[:, 2]
        np_final_grades = np_grades[:, 3]
        average = self._calculate_course_grade(
            np_grade_values,
            np_final_grades,
            np_mp_weights,
            marking_periods=marking_periods,
        )
        result = grade = self._round(average)
        if letter is True:
            result = letter_grade = GradeScaleRule.grade_to_scale(
                grade, np_mp[0], letter=True)
            if letter_and_number is True:
                result = '{} ({})'.format(grade, letter_grade)
        return result

    def get_student_gpa(self, student, date=None):
        """ Return student gpa

        Args:
            student: Student for gpa
            date: Date of report - used to exclude grades that haven't happened
        """
        grades = self._get_student_grades(student, date)
        return self._get_average_of_grades(grades)

    def get_year_average(self, student, year, date=None):
        grades = self._get_student_grades(student, date)
        grades = grades.filter(
            enrollment__course_section__marking_period__school_year=year)
        return self._get_average_of_grades(grades)

    def get_marking_period_average(self, student, marking_period):
        student.grade